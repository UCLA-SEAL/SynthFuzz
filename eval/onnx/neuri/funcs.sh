temp_dir=$(mktemp -d $temp_dir.XXXXX)
trap 'rm -rf "$temp_dir"' EXIT

eval_test_cases() {
    mkdir -p $eval_log_dir
    mkdir -p $cov_batch_dir

    python -m mlirmut.scripts.mlir_test_harness \
        $generate_dir \
        $eval_log_dir \
        "$target_binary" \
        --cov-batch-dir $cov_batch_dir \
        --temp-dir $temp_dir \
        --batch-size $eval_batch_size \
        --max-options $max_options \
        --association-file $association_file \
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
