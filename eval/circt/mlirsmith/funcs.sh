temp_dir=$(mktemp -d $temp_dir.XXXXX)
trap 'rm -rf "$temp_dir"' EXIT

generate_test_cases() {
    mkdir -p $generate_dir
    mkdir -p $log_dir

    # Generate until 100000 test cases or 2hrs seconds have passed
    start_time=$(date +%s)
    for i in {1..100000}
    do
        echo "Generating $i"
        $mlirsmith -d &> "$generate_dir/$i.mlir"
        total_time=$(($(date +%s) - $start_time))
        if [ $total_time -gt 7200 ]; then
            echo "Timed out after $total_time seconds"
            break
        fi
    done
    total_time=$(($(date +%s) - $start_time))
    echo "{\"total_time\": $total_time}" > "$log_dir/gen.json"
}

clean_test_cases() {
    src_dir="$generate_dir"
    dest_dir="$gen_cleaned_dir"

    mkdir -p $dest_dir

    for file in $src_dir/*.mlir
    do
        base=$(basename "$file")
        sed -n '/^module\|^"builtin/,$p' $file > $dest_dir/$base
    done
}

eval_test_cases() {
    mkdir -p $eval_log_dir
    mkdir -p $cov_batch_dir

    python -m mlirmut.scripts.mlir_test_harness \
        $gen_cleaned_dir \
        $eval_log_dir \
        "$target_binary" \
        --cov-batch-dir $cov_batch_dir \
        --temp-dir $temp_dir \
        --batch-size $eval_batch_size \
        --max-options $max_options \
        --association-file $association_file \
        --random-mode \
        --seed 2024
}

postprocess_cov() {
    echo Accumulating coverage
    python -m mlirmut.scripts.accumulate_cov \
        $cov_batch_dir \
        $cov_cumulative_dir \
        --unnumbered

    echo Exporting
    python -m mlirmut.scripts.export_cov_summary \
        $cov_cumulative_dir \
        $cov_summary_dir \
        --target-binary $target_binary \
        --timeout 200 # export takes much longer than usual for mlir-opt
}

filter_inputs() {
    mkdir -p $gen_filtered_dir
    python -m mlirmut.scripts.filter_inputs $gen_cleaned_dir $gen_filtered_dir --oracle-tmplt "$oracle"
}

compute_pairs() {
    python -m mlirmut.scripts.compute_pairs $gen_filtered_dir -o $diversity_path
}