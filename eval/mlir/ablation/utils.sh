temp_dir=$(mktemp -d $temp_dir.XXXXX)
trap 'rm -rf "$temp_dir"' EXIT

generate_test_cases() {
    mkdir -p $working_seed_pop_dir
    cp -r $original_seed_pop_dir/* $working_seed_pop_dir

    mkdir -p $edit_log_dir
    mkdir -p $generate_dir


    echo "Start time: $(date)" >> $generate_log
    python -m mlirmut.synthfuzz.generate \
        mlir_2023Generator.mlir_2023Generator \
        -r start_rule \
        -d $depth \
        -o $generate_dir/%d.mlir \
        -n $count \
        --sys-path $generator_code_dir \
        --population $working_seed_pop_dir \
        --insert-patterns $insert_patterns \
        --mutation-config $mutation_config \
        --edit-log $edit_log_dir \
        --keep-trees \
        $disabled_strategies \
        $context_options
    echo "Stop time: $(date)" >> $generate_log
}

eval_test_cases() {
    mkdir -p $eval_log_dir
    mkdir -p $cov_batch_dir

    python -m mlirmut.scripts.mlir_test_harness \
        $generate_dir \
        $eval_log_dir \
        "$target_binary" \
        --cov-batch-dir $cov_batch_dir \
        --temp-dir $temp_dir \
        --batch-size 50 \
        --save-stderr \
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

compute_pairs() {
    computepairs -w 32 --mlir-opt-path /workdir/llvm-project/build/bin/mlir-opt -o $diversity_path $generate_dir 
}