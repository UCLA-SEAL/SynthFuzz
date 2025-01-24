"builtin.module"() ({
  "func.func"() <{function_type = (i8, i8) -> i64, sym_name = "andOfExtSI"}> ({
  ^bb0(%arg0: i8, %arg1: i8):
    %0 = "arith.extsi"(%arg0) : (i8) -> i64
    %1 = "arith.extsi"(%arg1) : (i8) -> i64
    %2 = "arith.andi"(%0, %1) : (i64, i64) -> i64
    "func.return"(%2) : (i64) -> ()
  }) : () -> ()
  "func.func"() <{function_type = (i8, i8) -> i64, sym_name = "andOfExtUI"}> ({
  ^bb0(%arg0: i8, %arg1: i8):
    %0 = "arith.extui"(%arg0) : (i8) -> i64
    %1 = "arith.extui"(%arg1) : (i8) -> i64
    %2 = "arith.andi"(%0, %1) : (i64, i64) -> i64
    "func.return"(%2) : (i64) -> ()
  }) : () -> ()
  "func.func"() <{function_type = (i8, i8) -> i64, sym_name = "orOfExtSI"}> ({
  ^bb0(%arg0: i8, %arg1: i8):
    %0 = "arith.extsi"(%arg0) : (i8) -> i64
    %1 = "arith.extsi"(%arg1) : (i8) -> i64
    %2 = "arith.ori"(%0, %1) : (i64, i64) -> i64
    "func.return"(%2) : (i64) -> ()
  }) : () -> ()
  "func.func"() <{function_type = (i8, i8) -> i64, sym_name = "orOfExtUI"}> ({
  ^bb0(%arg0: i8, %arg1: i8):
    %0 = "arith.extui"(%arg0) : (i8) -> i64
    %1 = "arith.extui"(%arg1) : (i8) -> i64
    %2 = "arith.ori"(%0, %1) : (i64, i64) -> i64
    "func.return"(%2) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

