grammar mlir_2023;

bool_literal : TRUE | FALSE ;
decimal_literal : DIGITS ;
HEXADECIMAL_LITERAL : '0x' [0-9a-fA-F]+ ;
integer_literal : decimal_literal | HEXADECIMAL_LITERAL ;
negated_integer_literal : '-' integer_literal ;
posneg_integer_literal : integer_literal | negated_integer_literal ;
string_literal  : ESCAPED_STRING ;
constant_literal : bool_literal | integer_literal | FLOAT_LITERAL | string_literal ;

// Identifier syntax
suffix_id : DIGITS | BARE_ID ;

// Dimensions
DIMENSION_ENTRY : ('?' | DIGITS) 'x' ;
static_dimension_list   : (decimal_literal 'x')+ ;
dimension_list_ranked   : (DIMENSION_ENTRY)+ ;
DIMENSION_LIST_UNRANKED : '*x' ;
dimension_list : dimension_list_ranked | DIMENSION_LIST_UNRANKED ;

// ----------------------------------------------------------------------
// Identifiers

ssa_id        : '%' suffix_id ('#' DIGITS)? ;
symbol_ref_id : '@' (suffix_id | string_literal) ;
block_id      : '^' suffix_id ;
type_alias     : '!' (string_literal | BARE_ID) ;
map_or_set_id : '#' suffix_id ;
attribute_alias : '#' (string_literal | BARE_ID) ;

ssa_id_list : ssa_id (',' ssa_id)* ;

// Uses of an SSA value, e.g., in an operand list to an operation.
ssa_use : ssa_id | constant_literal ;
ssa_use_list : ssa_use (',' ssa_use)* ;

// ----------------------------------------------------------------------
// Types

// Standard types
none_type : NONE_TYPE_LITERAL ;
index_type : INDEX_TYPE_LITERAL ;
// Sized integers like i1, i4, i8, i16, i32. 
SIGNED_INTEGER_TYPE : 'si' NONZERO_DIGIT DIGITS? ;
UNSIGNED_INTEGER_TYPE : 'ui' NONZERO_DIGIT DIGITS? ;
SIGNLESS_INTEGER_TYPE : 'i' NONZERO_DIGIT DIGITS? ;
float_type : FLOAT_TYPE_LITERAL ;
integer_type : SIGNED_INTEGER_TYPE | UNSIGNED_INTEGER_TYPE | SIGNLESS_INTEGER_TYPE ;
complex_type : 'complex' '<' type '>' ;
tuple_type : 'tuple' '<' type_list_no_parens '>' ;

// Vector types
vector_element_type : float_type | integer_type ;
vector_type : 'vector' '<' static_dimension_list vector_element_type '>' ;

// Tensor type
tensor_memref_element_type : vector_element_type | vector_type | complex_type | type_alias ;
ranked_tensor_type : 'tensor' '<' dimension_list_ranked? tensor_memref_element_type '>' ;
unranked_tensor_type : 'tensor' '<' DIMENSION_LIST_UNRANKED? tensor_memref_element_type '>' ;
tensor_type : ranked_tensor_type | unranked_tensor_type ;

// Memref type
stride_list : '[' (('?' | DIGITS) (',' ('?' | DIGITS))*)? ']' ;
strided_layout : 'offset:' ('?' | DIGITS) ',' 'strides: ' stride_list ;
layout_specification : semi_affine_map | strided_layout ;
memory_space : integer_literal ;
ranked_memref_type : 'memref' '<' dimension_list_ranked tensor_memref_element_type  optional_layout_specification optional_memory_space '>' ;
unranked_memref_type : 'memref' '<' DIMENSION_LIST_UNRANKED tensor_memref_element_type optional_memory_space '>' ;
memref_type : ranked_memref_type | unranked_memref_type ;

// Dialect types - these can be opaque, pretty, or using custom dialects
opaque_dialect_item : BARE_ID '<' string_literal '>' ;
pretty_dialect_item : BARE_ID '.' (BARE_ID | NONE_TYPE_LITERAL) pretty_dialect_item_body? ;
pretty_dialect_item_body : '<' pretty_dialect_item_contents (',' pretty_dialect_item_contents)* '>' ;
pretty_dialect_item_contents : ('(' pretty_dialect_item_contents ')')
                              | ('[' pretty_dialect_item_contents ']')
                              | ('{' pretty_dialect_item_contents '}')
                              | BARE_ID
                              | constant_literal
                              | stride_list
                              | type ;

// NOTE: 'pymlir_dialect_types' is defined externally by pyMLIR
dialect_type : '!' (opaque_dialect_item | pretty_dialect_item) ;

// Final type definition
standard_type     : complex_type | float_type | function_type | llvm_function_type | index_type | integer_type | memref_type | none_type | tensor_type | tuple_type | vector_type ;
non_function_type : type_alias | complex_type | float_type | index_type | integer_type | memref_type | none_type | tensor_type | tuple_type | vector_type | dialect_type ;
type              : type_alias | dialect_type | standard_type ;

// Uses of types
type_list_no_parens :  type (',' type)* ;
non_function_type_list_no_parens : non_function_type (',' non_function_type)* ;
type_list_parens : ('(' ')') | ('(' type_list_no_parens ')') ;
non_function_type_list_parens : ('(' ')') | ('(' non_function_type_list_no_parens ')') ;
function_result_type : non_function_type_list_parens | non_function_type_list_no_parens | non_function_type ;
function_type : function_result_type ('->' | 'to' | 'into') function_result_type ;
llvm_function_type : non_function_type non_function_type_list_parens ;
ssa_use_and_type : ssa_use ':' type ;
ssa_use_and_type_list : ssa_use_and_type (',' ssa_use_and_type)* ;

// ----------------------------------------------------------------------
// Attributes

// Simple attribute types
array_attribute : '[' (attribute_value (',' attribute_value)*)? ']' ;
bool_attribute : bool_literal ;
dictionary_attribute : '{' (attribute_entry (',' attribute_entry)*)? '}' ;
elements_attribute : dense_elements_attribute | opaque_elements_attribute | sparse_elements_attribute ;
float_attribute : (FLOAT_LITERAL optional_float_type) | (HEXADECIMAL_LITERAL ':' float_type) ;
integer_attribute : posneg_integer_literal optional_int_type ;
integer_set_attribute : affine_map ;
string_attribute : string_literal optional_type ;
symbol_ref_attribute : (symbol_ref_id ('::' symbol_ref_id)*) ;
type_attribute : type ;
unit_attribute : 'unit';


// Elements attribute types
dense_elements_attribute : 'dense' '<' attribute_value '>' ':' ( tensor_type | vector_type ) ;
opaque_elements_attribute : 'opaque' '<' BARE_ID  ',' HEXADECIMAL_LITERAL '>' ':' ( tensor_type | vector_type ) ;
sparse_elements_attribute : 'sparse' '<' attribute_value ',' attribute_value '>' ':' ( tensor_type | vector_type ) ;

// Standard attributes
standard_attribute : array_attribute | bool_attribute | dictionary_attribute | elements_attribute | float_attribute | integer_attribute | integer_set_attribute | string_attribute | symbol_ref_attribute | type_attribute | unit_attribute ;

// Attribute values
attribute_value : attribute_alias | dialect_attribute | standard_attribute ;
unit_attribute_entry : 'value' ;
dependent_attribute_entry : (BARE_ID | unit_attribute_entry) '=' attribute_value ;
dialect_attribute_entry : (BARE_ID '.' BARE_ID) | (BARE_ID '.' BARE_ID '=' attribute_value) | (string_literal '=' attribute_value) ;

// Dialect attributes
dialect_attribute : '#' (opaque_dialect_item | pretty_dialect_item) ;

// Property dictionaries
property_dict : '<' attribute_dict '>' ;

// Attribute dictionaries
attribute_entry : dialect_attribute_entry | dependent_attribute_entry | unit_attribute_entry ;
attribute_dict : ('{' '}') | ('{' attribute_entry (',' attribute_entry)* '}') ;

// ----------------------------------------------------------------------
// Operations

// Types that appear after the operation, indicating return types
trailing_type     : ':' (function_type | function_result_type) ;

// Operation results
op_result         : ssa_id optional_int_literal ;
op_result_list    : op_result (',' op_result)* '=' ;

// Trailing location (for debug information)
location : string_literal ':' decimal_literal ':' decimal_literal ;
trailing_location : ('loc' '(' location ')') ;

// Undefined operations in all dialects
generic_operation : string_literal '(' optional_ssa_use_list ')' optional_successor_list optional_prop_dict optional_region_list optional_attr_dict trailing_type ;
custom_operation  : BARE_ID '.' BARE_ID optional_ssa_use_list trailing_type ;

// Final operation definition
// NOTE: 'pymlir_dialect_ops' is defined externally by pyMLIR
operation         : optional_op_result_list (custom_operation | generic_operation | module | generic_module | function) optional_trailing_loc ;

// ----------------------------------------------------------------------
// Blocks and regions

// Block arguments
ssa_id_and_type : ssa_id ':' type ;
ssa_id_and_type_list : ssa_id_and_type (',' ssa_id_and_type)* ;
block_arg_list : '(' optional_ssa_and_type_list ')' ;
operation_list: operation+ ;

block_label     : block_id optional_block_arg_list ':' ;
successor_list   : '[' block_id? (',' block_id)* ']' ;

block           : optional_block_label operation_list ;
region : '{' block* '}' ;
region_list : '(' region? (',' region)* ')' ;

// --------------------------------------------------------------------- ;
// Optional types ;
optional_symbol_ref_id                 : symbol_ref_id? ;
optional_func_mod_attrs                : ('attributes' attribute_dict)? ;
optional_arg_list                      : argument_list? ;
optional_fn_result_list                : ('->' function_result_list)? ;
optional_fn_body                       : function_body? ;
optional_symbol_id_list                : symbol_id_list? ;
optional_affine_constraint_conjunction : affine_constraint_conjunction? ;
optional_float_type                    : (':' float_type)? ;
optional_int_type                      : ( ':' (index_type | integer_type) )? ;
optional_type                          : (':' type)? ;
optional_int_literal                   : (':' integer_literal)? ;
optional_ssa_use_list                  : ssa_use_list? ;
optional_prop_dict                     : property_dict? ;
optional_attr_dict                     : attribute_dict? ;
optional_trailing_loc                  : trailing_location? ;
optional_op_result_list                : op_result_list? ;
optional_ssa_and_type_list             : ssa_id_and_type_list? ;
optional_block_arg_list                : block_arg_list? ;
optional_layout_specification          : (',' layout_specification)? ;
optional_memory_space                  : (',' memory_space)? ;
optional_block_label                   : block_label? ;
optional_symbol_use_list               : symbol_use_list? ;
optional_successor_list                : successor_list? ;
optional_region_list                   : region_list? ;
// ----------------------------------------------------------------------
// Modules and functions

// Arguments
named_argument : ssa_id ':' type optional_attr_dict ;
argument_list : (named_argument (',' named_argument)*) | (type optional_attr_dict (',' type optional_attr_dict)*) ;

// Return values
function_result : type optional_attr_dict ;
function_result_list_no_parens : function_result (',' function_result)* ;
function_result_list_parens : ('(' ')') | ('(' function_result_list_no_parens ')') ;
function_result_list : function_result_list_parens | non_function_type ;

// Body
function_body : region ;

// Definition
module : 'module' optional_symbol_ref_id optional_func_mod_attrs region optional_trailing_loc ;
function : 'func.func' symbol_ref_id '(' optional_arg_list ')' optional_fn_result_list optional_func_mod_attrs optional_fn_body optional_trailing_loc ;
generic_module : string_literal '(' argument_list? ')' '(' region ')' attribute_dict? trailing_type trailing_location? ;

// ----------------------------------------------------------------------
// (semi-)affine expressions, maps, and integer sets

dim_id_list : '(' BARE_ID? (',' BARE_ID)* ')' ;
symbol_id_list: '[' BARE_ID? (',' BARE_ID)* ']' ;
dim_and_symbol_id_lists : dim_id_list optional_symbol_id_list ;
symbol_or_const : posneg_integer_literal | ssa_id | BARE_ID ;

dim_use_list    : '(' ssa_use_list? ')' ;
symbol_use_list : '[' ssa_use_list? ']' ;
dim_and_symbol_use_list : dim_use_list optional_symbol_use_list ;

affine_expr : '(' affine_expr ')'
            | affine_expr '+' affine_expr
            | affine_expr '-' affine_expr
            | posneg_integer_literal '*' affine_expr
            | affine_expr '*' posneg_integer_literal
            | affine_expr '&ceildiv&' integer_literal
            | affine_expr '&floordiv&' integer_literal
            | affine_expr '&mod&' integer_literal
            | '-' affine_expr
            | 'symbol' '(' ssa_id ')'
            | posneg_integer_literal
            | ssa_id
            | BARE_ID ;

semi_affine_expr : '(' semi_affine_expr ')'
                 | semi_affine_expr '+' semi_affine_expr
                 | semi_affine_expr '-' semi_affine_expr
                 | symbol_or_const '*' semi_affine_expr
                 | semi_affine_expr '*' symbol_or_const
                 | semi_affine_expr '&ceildiv&' semi_affine_oprnd
                 | semi_affine_expr '&floordiv&' semi_affine_oprnd
                 | semi_affine_expr '&mod&' semi_affine_oprnd
                 | 'symbol' '(' symbol_or_const ')'
                 | symbol_or_const ;
// Second operand for floordiv/ceildiv/mod in semi-affine expressions ;
semi_affine_oprnd : symbol_or_const
                   | '(' semi_affine_expr ')' ;

multi_dim_affine_expr_no_parens : affine_expr (',' affine_expr)* ;
multi_dim_semi_affine_expr_no_parens : semi_affine_expr (',' semi_affine_expr)* ;
multi_dim_affine_expr : '(' multi_dim_affine_expr_no_parens ')' ;
multi_dim_semi_affine_expr : '(' multi_dim_semi_affine_expr_no_parens ')' ;
affine_constraint : affine_expr '>=' DIGIT
                  | affine_expr '==' DIGIT ;
affine_constraint_conjunction : affine_constraint (',' affine_constraint)* ;

affine_map_inline      : 'affine_map' '<' dim_and_symbol_id_lists '->' multi_dim_affine_expr '>' ;
semi_affine_map_inline : dim_and_symbol_id_lists '->' multi_dim_semi_affine_expr ;
integer_set_inline     : dim_and_symbol_id_lists ':' '(' optional_affine_constraint_conjunction ')' ;

// Definition of maps and sets ;
affine_map      : map_or_set_id | affine_map_inline ;
semi_affine_map : map_or_set_id | semi_affine_map_inline ;
integer_set     : map_or_set_id | integer_set_inline ;

affine_map_list : affine_map (',' affine_map)* ;

// ----------------------------------------------------------------------
// General structure and top-level definitions

// Definitions of affine maps/integer sets/aliases are at the top of the file
type_alias_def : type_alias '=' 'type' type ;
affine_map_def      : map_or_set_id '=' affine_map_inline ;
semi_affine_map_def : map_or_set_id '=' semi_affine_map_inline ;
integer_set_def     : map_or_set_id '=' integer_set_inline ;
attribute_alias_def : attribute_alias '=' attribute_value ;
definition : type_alias_def | affine_map_def | semi_affine_map_def | integer_set_def | attribute_alias_def ;

// ----------------------------------------------------------------------
// Structure of an MLIR parse-able string

definition_list              : definition+ ;
function_list                : function+ ;
module_list                  : (module | generic_module)+ ;
definition_and_function_list : definition_list | function_list | definition_list function_list;
definition_and_module_list   : definition_list | module_list | definition_list module_list ;

mlir_file: definition_and_function_list+
         | definition_and_module_list+ ;

start_rule: mlir_file ;

// Tokens
ESCAPED_STRING
    : ([uUbB]? [rR]? | [rR]? [uUbB]?)
    ( '\''     ('\\' (([ \t]+ ('\r'? '\n')?)|.) | ~[\\\r\n'])*  '\''
    | '"'      ('\\' (([ \t]+ ('\r'? '\n')?)|.) | ~[\\\r\n"])*  '"'
    | '"""'    ('\\' .                          | ~'\\'     )*? '"""'
    | '\'\'\'' ('\\' .                          | ~'\\'     )*? '\'\'\''
    )
    ;


NONE_TYPE_LITERAL : 'none' ;
INDEX_TYPE_LITERAL : 'index' ;
FLOAT_TYPE_LITERAL : 'f16' | 'bf16' | 'f32' | 'f64' ;

FLOAT_LITERAL : [-+]?[0-9]+[.][0-9]*([eE][-+]?[0-9]+)? ;
DIGITS : DIGIT+ ;
NONZERO_DIGIT : [1-9] ;
DIGIT : [0-9] ;
LETTER     : [a-zA-Z] ;
TRUE       : 'true' ;
FALSE      : 'false' ;
ID_CHARS : [$] ;
BARE_ID : (LETTER | '_') (LETTER|DIGIT|'_'|ID_CHARS)* ;

WS : [ \t\r\n]+ -> skip ;
