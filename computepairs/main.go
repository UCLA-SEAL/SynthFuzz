package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/spf13/cobra"
)

type DecomposedOp struct {
	IndentLevel   int
	ReturnValues  []string
	OperandValues []string
	FullName      string
	Dialect       string
}

type DeferredOp struct {
	LineIdx int
	Line    string
	Op      *DecomposedOp
}

type ValOrigin struct {
	FullName string
	Indent   int
}

type Deps map[string]map[string]struct{}

type PairResult struct {
	Control Deps
	Data    Deps
	err     error
}

var (
	outputPath  string
	cacheDir    string
	mlirOptPath string
	maxWorkers  int
	batchSize   int
	rootCmd     = &cobra.Command{
		Use:   "computepairs",
		Short: "Compute operation pairs with control and data dependencies",
		Long:  "A tool to compute operation pairs with control and data dependencies in MLIR code",
		Args:  cobra.ExactArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			inputDir := args[0]
			// Check that the input directory exists and is a directory
			if inputStat, err := os.Stat(inputDir); os.IsNotExist(err) {
				fmt.Println("Input directory does not exist")
				os.Exit(1)
			} else if !inputStat.IsDir() {
				fmt.Println("Input path is not a directory")
				os.Exit(1)
			} else if err != nil {
				fmt.Println("Error checking input directory:", err)
				os.Exit(1)
			}
			controlDeps, dataDeps := computeDepsDir(inputDir, mlirOptPath)
			jsonDeps, err := jsonifyDeps(controlDeps, dataDeps)
			if err != nil {
				log.Fatal(err)
			}
			os.WriteFile(outputPath, jsonDeps, 0644)
		},
	}
)

func computeDepsDir(inputDir, mlirOptPath string) (Deps, Deps) {
	files, err := filepath.Glob(filepath.Join(inputDir, "*.mlir"))
	if err != nil {
		log.Fatal(err)
	}
	allControlDeps := make(Deps)
	allDataDeps := make(Deps)

	var wg sync.WaitGroup
	resultChan := make(chan PairResult)

	// Create a buffered channel to act as a semaphore.
	sem := make(chan struct{}, maxWorkers)

	for i := 0; i < len(files); i += batchSize {
		wg.Add(1)
		endIdx := (i + 1) * batchSize
		if endIdx > len(files) {
			endIdx = len(files)
		}
		batchFiles := files[i:endIdx]

		go func(batchFiles []string) {
			defer wg.Done()

			// Acquire a token from the semaphore.
			sem <- struct{}{}

			controlDeps, dataDeps, err := computeDepsBatch(batchFiles, mlirOptPath)

			resultChan <- PairResult{
				Control: controlDeps,
				Data:    dataDeps,
				err:     err,
			}

			// Release the token back to the semaphore.
			<-sem
		}(batchFiles)
	}

	go func() {
		wg.Wait()
		close(resultChan)
	}()

	startTime := time.Now()
	numProcessed := 0
	for result := range resultChan {
		if result.err == nil {
			mergeDeps(allControlDeps, result.Control)
			mergeDeps(allDataDeps, result.Data)
		} else {
			fmt.Printf("\nError computing deps:\n%v\n", result.err)
		}
		numProcessed++
		elapsedTime := time.Since(startTime)
		filesPerSec := float64(numProcessed) / elapsedTime.Seconds()
		remainingFiles := len(files) - numProcessed
		remainingTime := time.Duration(float64(remainingFiles) / filesPerSec * float64(time.Second))
		fmt.Printf("\rProcessed %d/%d files; Elapsed: %v; Remaining %v", numProcessed, len(files), elapsedTime, remainingTime)
	}

	return allControlDeps, allDataDeps
}

func mergeDeps(allDeps, deps Deps) {
	for newKey, newDeps := range deps {
		if _, ok := allDeps[newKey]; !ok {
			allDeps[newKey] = make(map[string]struct{})
		}
		for v := range newDeps {
			allDeps[newKey][v] = struct{}{}
		}
	}
}

func computeDepsBatch(files []string, mlirOptPath string) (Deps, Deps, error) {
	// Catch and print panics
	defer func() {
		if err := recover(); err != nil {
			fmt.Println("Panic in files: ", files)
			fmt.Println(err)
		}
	}()
	// Read each file
	rawMLIRs := make([]string, len(files))
	for i, file := range files {
		rawMLIR, err := os.ReadFile(file)
		if err != nil {
			panic(err)
		}
		rawMLIRs[i] = string(rawMLIR)
	}
	// Batch format
	formattedMLIRs, err := formatBatch(rawMLIRs, mlirOptPath)
	if err != nil {
		return nil, nil, err
	}
	batchControlDeps := make(Deps)
	batchDataDeps := make(Deps)
	var cumulativeErrs error = nil
	for i, formattedMLIR := range formattedMLIRs {
		controlDeps, dataDeps, err := computeOpPairs(formattedMLIR)
		if err != nil {
			cumulativeErrs = fmt.Errorf("errors in file: %s\n%w;\n%w", files[i], cumulativeErrs, err)
			continue
		}
		mergeDeps(batchControlDeps, controlDeps)
		mergeDeps(batchDataDeps, dataDeps)
	}
	return batchControlDeps, batchDataDeps, cumulativeErrs
}

func computeDepsFile(filepath, mlirOptPath string) (Deps, Deps, error) {
	rawMLIR, err := os.ReadFile(filepath)
	if err != nil {
		return nil, nil, err
	}
	formattedMLIR, err := formatMLIR(string(rawMLIR), mlirOptPath)
	if err != nil {
		return nil, nil, err
	}
	return computeOpPairs(formattedMLIR)
}

func jsonifyDeps(controlDeps, dataDeps Deps) ([]byte, error) {
	allDeps := make(map[string]map[string][]string)
	allDeps["control"] = serializedDeps(controlDeps)
	allDeps["data"] = serializedDeps(dataDeps)
	return json.Marshal(allDeps)
}

func serializedDeps(deps Deps) map[string][]string {
	serializedDeps := make(map[string][]string)
	for k, v := range deps {
		serializedDeps[k] = make([]string, 0, len(v))
		for vv := range v {
			serializedDeps[k] = append(serializedDeps[k], vv)
		}
	}
	return serializedDeps
}

func formatBatch(rawMLIRs []string, mlirOptPath string) ([]string, error) {
	// Initially try concatenating everything,
	// then fall back to formatting invidiually if we get a crash
	combinedMLIR := ""
	for i, rawMLIR := range rawMLIRs {
		combinedMLIR += rawMLIR
		if i < len(rawMLIRs)-1 {
			combinedMLIR += "\n// -----\n"
		}
	}

	// Define the command and arguments
	cmd := exec.Command(mlirOptPath,
		"--mlir-print-op-generic",
		"--allow-unregistered-dialect",
		"--split-input-file",
	)
	cmd.Stdin = bytes.NewBufferString(combinedMLIR)

	// Capture the standard output and standard error
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// Run the command
	err := cmd.Run()
	// If we get a crash, then we must format individually
	crashed := false
	if err != nil {
		if exitError, ok := err.(*exec.ExitError); ok {
			// consider 1 a success
			if exitError.ExitCode() != 1 {
				// If the command fails, log the standard error and return the error
				crashed = true
			}
		} else {
			// If it's not an ExitError
			crashed = true
		}
	}
	if crashed {
		formattedMLIRs := make([]string, len(rawMLIRs))
		for i, rawMLIR := range rawMLIRs {
			formattedMLIR, err := formatMLIR(rawMLIR, mlirOptPath)
			if err != nil {
				continue
			}
			formattedMLIRs[i] = formattedMLIR
		}
		return formattedMLIRs, nil
	}

	// Resplit back into individual files since we don't want an error in one file to affect another
	return strings.Split(stdout.String(), "// -----"), nil
}

func formatMLIR(text, mlirOptPath string) (string, error) {
	// Define the command and arguments
	cmd := exec.Command(mlirOptPath,
		"--mlir-print-op-generic",
		"--allow-unregistered-dialect",
	)

	// Set the input for the command
	cmd.Stdin = bytes.NewBufferString(text)

	// Capture the standard output and standard error
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// Run the command
	err := cmd.Run()
	if err != nil {
		// If the command fails, log the standard error and return the error
		//log.Println(stderr.String())
		return "", fmt.Errorf("mlir-opt failed: %w", err)
	}

	// Return the standard output
	return stdout.String(), nil
}

type OpParseError struct {
	Expected bool
	Line     string
	Msg      string
}

func (e *OpParseError) Error() string {
	expectedStr := "unexpected"
	if e.Expected {
		expectedStr = "expected"
	}
	return fmt.Sprintf("%v failure to parse operation: %s: %s", expectedStr, e.Line, e.Msg)
}

var (
	returnValuesRegex  = regexp.MustCompile(`%([^\s,:]+)`)
	fullNameRegex      = regexp.MustCompile(`"(.+?)"`)
	operandSubstrRegex = regexp.MustCompile(`\((.*?)\)`)
	operandValuesRegex = regexp.MustCompile(`%([^\s,:#]+)`)
	commentRegex       = regexp.MustCompile(`^\s*\/\/`)
)

func decomposeOp(line string) (*DecomposedOp, error) {
	// Remove leading spaces
	strippedLine := strings.TrimLeft(line, " ")

	// First check if it's even an operation by looking for either a '%' or a '"'
	if !(strings.HasPrefix(strippedLine, "%") || strings.HasPrefix(strippedLine, "\"")) {
		return nil, &OpParseError{true, line, "not an operation"}
	}

	// Compute the indent level by counting the number of spaces at the beginning of the line and dividing by 2
	indentLevel := (len(line) - len(strippedLine)) / 2

	// Extract any return values
	returnValuesSubstr := strippedLine[:strings.Index(strippedLine, "\"")]
	returnValues := returnValuesRegex.FindAllStringSubmatch(returnValuesSubstr, -1)

	// Extract the operation name and dialect
	fullNameMatch := fullNameRegex.FindStringSubmatch(strippedLine)
	if fullNameMatch == nil {
		return nil, &OpParseError{false, line, "failed to extract operation name"}
	}
	fullName := fullNameMatch[1]
	if !strings.Contains(fullName, ".") || strings.Contains(fullName, " ") {
		return nil, &OpParseError{false, line, "operation name is improperly formatted"}
	}
	dialect := fullName[:strings.Index(fullName, ".")]

	// Extract any operands
	operandSubstrMatch := operandSubstrRegex.FindStringSubmatch(strippedLine)
	if operandSubstrMatch == nil {
		return nil, &OpParseError{false, line, "failed to extract operands"}
	}
	operandSubstr := operandSubstrMatch[1]
	operandValues := operandValuesRegex.FindAllStringSubmatch(operandSubstr, -1)

	decomposedOp := &DecomposedOp{
		IndentLevel:   indentLevel,
		ReturnValues:  flattenStrings(returnValues),
		OperandValues: flattenStrings(operandValues),
		FullName:      fullName,
		Dialect:       dialect,
	}

	return decomposedOp, nil
}

func flattenStrings(matches [][]string) []string {
	var result []string
	for _, match := range matches {
		result = append(result, match[1])
	}
	return result
}

func decomposeBlockLabel(line string) ([]string, error) {
	// Remove leading spaces
	strippedLine := strings.TrimLeft(line, " ")

	// First check if it's a block label by looking for a '^'
	if !strings.HasPrefix(strippedLine, "^") {
		return nil, &OpParseError{true, line, "not a block label"}
	}

	// Extract any operands
	operandSubstrMatch := operandSubstrRegex.FindStringSubmatch(strippedLine)
	if operandSubstrMatch == nil {
		return []string{}, nil // block label does not have any operands
	}
	operandSubstr := operandSubstrMatch[1]
	operandValues := operandValuesRegex.FindAllStringSubmatch(operandSubstr, -1)

	return flattenStrings(operandValues), nil
}

func computeOpPairs(formattedMLIR string) (Deps, Deps, error) {
	controlDeps := make(Deps)
	dataDeps := make(Deps)
	currentIndent := 0
	parentOps := []*DecomposedOp{}
	prevOp := (*DecomposedOp)(nil)
	valueMap := make(map[string]ValOrigin)
	deferredOps := []*DeferredOp{}
	var nonFatalErrs error = nil

	lines := strings.Split(formattedMLIR, "\n")
	for lineIdx, line := range lines {
		// If it's a comment, skip
		if commentRegex.MatchString(line) {
			continue
		}
		op, err := decomposeOp(line)

		var e *OpParseError
		if err != nil {
			if errors.As(err, &e) {
				if !e.Expected {
					fmt.Println(e)
					nonFatalErrs = fmt.Errorf("%w;\n%w", nonFatalErrs, e)
				} // otherwise just continue normally
			} else {
				// If it's not an OpParseError, then it's a fatal error
				return nil, nil, err
			}
		}
		if op == nil {
			// If it was an expected error, then it may be a block label
			possibleArgs, _ := decomposeBlockLabel(line)
			if possibleArgs == nil {
				continue // Not a block label, go to the next line
			}
			if prevOp == nil {
				// Fatal error because we cannot associate the block arguments with operation
				return nil, nil, fmt.Errorf("block label without associated operation on line %d: %s", lineIdx, line)
			}
			for _, arg := range possibleArgs {
				if _, exists := valueMap[arg]; !exists {
					// the value is only visible in the next block (one indent in)
					valueMap[arg] = ValOrigin{prevOp.FullName, prevOp.IndentLevel + 1}
				}
			}
			continue
		}

		// when we reach a new indent, then we should set the parent
		// operation to the previous operation
		if op.IndentLevel > currentIndent {
			if prevOp == nil {
				// Fatal error because the indent increased without a parent operation
				return nil, nil, fmt.Errorf("indent without associated operation on line %d: %s", lineIdx, line)
			}
			parentOps = append(parentOps, prevOp)
			currentIndent = op.IndentLevel
		} else if op.IndentLevel < currentIndent {
			// Add data dependencies for deferred operations
			for _, dOp := range deferredOps {
				for _, operand := range dOp.Op.OperandValues {
					if _, exists := valueMap[operand]; !exists {
						// Fatal error because the operand is not in the value map
						return nil, nil, fmt.Errorf("failed to find mapping for operand `%s` in line %d: `%s`", operand, dOp.LineIdx, dOp.Line)
					}
					if _, exists := dataDeps[dOp.Op.FullName]; !exists {
						dataDeps[dOp.Op.FullName] = make(map[string]struct{})
					}
					dataDeps[dOp.Op.FullName][valueMap[operand].FullName] = struct{}{}
				}
			}
			// remove deferred operations that are at a higher indent than we are
			// now since there are no other possible values they can reference
			deferredOps = filterDeferredOps(deferredOps, op.IndentLevel)
			// remove parent ops and values that are no longer visible
			parentOps = parentOps[:len(parentOps)-1]
			// remove values that are no longer visible
			filterValueMap(&valueMap, op.IndentLevel)
			currentIndent = op.IndentLevel
		}

		// Add control dependencies
		if _, exists := controlDeps[op.FullName]; !exists {
			controlDeps[op.FullName] = make(map[string]struct{})
		}
		for _, parentOp := range parentOps {
			controlDeps[op.FullName][parentOp.FullName] = struct{}{}
		}

		// Add data dependencies
		for _, operand := range op.OperandValues {
			if _, exists := valueMap[operand]; !exists {
				// the operand may refer to a later operation (graphs with cycles)
				deferredOps = append(deferredOps, &DeferredOp{LineIdx: lineIdx, Line: line, Op: op})
				continue
			}
			if _, exists := dataDeps[op.FullName]; !exists {
				dataDeps[op.FullName] = make(map[string]struct{})
			}
			dataDeps[op.FullName][valueMap[operand].FullName] = struct{}{}
		}

		// since its SSA, then we can assume there's a many-to-one mapping from return values to operations
		for _, retValue := range op.ReturnValues {
			if _, exists := valueMap[retValue]; !exists {
				valueMap[retValue] = ValOrigin{op.FullName, op.IndentLevel}
			}
		}

		prevOp = op
	}

	return controlDeps, dataDeps, nonFatalErrs
}

func filterDeferredOps(deferredOps []*DeferredOp, indentLevel int) []*DeferredOp {
	var filtered []*DeferredOp
	for _, dOp := range deferredOps {
		if dOp.Op.IndentLevel <= indentLevel {
			filtered = append(filtered, dOp)
		}
	}
	return filtered
}

func filterValueMap(valueMap *map[string]ValOrigin, indentLevel int) {
	for key, value := range *valueMap {
		if value.Indent > indentLevel {
			delete(*valueMap, key)
		}
	}
}

func init() {
	rootCmd.Flags().StringVarP(&outputPath, "output", "o", "", "Output file path")
	rootCmd.Flags().StringVarP(&cacheDir, "cache-dir", "c", "", "Cache directory path")
	rootCmd.Flags().StringVarP(&mlirOptPath, "mlir-opt-path", "m", "/workdir/llvm-project/build/bin/mlir-opt", "mlir-opt path")
	rootCmd.Flags().IntVarP(&maxWorkers, "max-workers", "w", 1, "Maximum number of workers")
	rootCmd.Flags().IntVarP(&batchSize, "batch-size", "b", 1, "Number of MLIR files per batch")
}

func main() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
