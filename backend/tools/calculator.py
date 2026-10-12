import ast
import operator


# ============================================================
# ALLOWED OPERATIONS
# ============================================================

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.FloorDiv: operator.floordiv,
}


# ============================================================
# SAFE CALCULATOR
# ============================================================

def calculate(expression: str):

    expression = expression.strip()

    if not expression:
        raise ValueError("Empty expression")


    # Parse mathematical expression
    tree = ast.parse(
        expression,
        mode="eval"
    )


    def evaluate(node):

        # Number
        if isinstance(
            node,
            ast.Constant
        ):

            if isinstance(
                node.value,
                (int, float)
            ):

                return node.value

            raise ValueError(
                "Invalid value"
            )


        # Binary operations
        if isinstance(
            node,
            ast.BinOp
        ):

            operator_type = type(
                node.op
            )

            if operator_type not in OPERATORS:

                raise ValueError(
                    "Operation not allowed"
                )

            left = evaluate(
                node.left
            )

            right = evaluate(
                node.right
            )

            return OPERATORS[
                operator_type
            ](
                left,
                right
            )


        # Positive / negative
        if isinstance(
            node,
            ast.UnaryOp
        ):

            operator_type = type(
                node.op
            )

            if operator_type not in OPERATORS:

                raise ValueError(
                    "Operation not allowed"
                )

            value = evaluate(
                node.operand
            )

            return OPERATORS[
                operator_type
            ](value)


        raise ValueError(
            "Invalid mathematical expression"
        )


    return evaluate(
        tree.body
    )