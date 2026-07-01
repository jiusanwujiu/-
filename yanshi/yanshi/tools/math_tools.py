"""
砚识工具 — 数学计算工具

提供安全的基础数学运算和单位转换。
权限级别: READ（纯计算，无副作用）
"""

import math
import re

from .base import Tool, ToolResult, ToolPermission


class MathEvalTool(Tool):
    """安全的数学表达式求值"""

    SAFE_FUNCTIONS = {
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
        "sqrt": math.sqrt, "pow": pow,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
        "ceil": math.ceil, "floor": math.floor,
        "pi": math.pi, "e": math.e,
        "factorial": math.factorial, "gcd": math.gcd,
    }

    def __init__(self):
        super().__init__(
            name="math_eval",
            description="安全求值数学表达式（支持 +-*/^% 和常用函数: sqrt/sin/cos/log/pi 等）",
            permission=ToolPermission.READ,
            parameters={
                "expression": {"type": "string", "description": "数学表达式，如 sqrt(16) + 2*3"},
                "precision": {"type": "integer", "description": "结果保留几位小数"},
            },
        )

    @classmethod
    def _sanitize(cls, expr: str) -> str:
        safe_pattern = re.compile(r"[^0-9+\-*/().%^\sa-zA-Z_]")
        return safe_pattern.sub("", expr).strip()

    def execute(self, **params) -> ToolResult:
        expr = params.get("expression", "")
        if not expr:
            return ToolResult(success=False, output="未提供表达式", error="empty input")

        expression = self._sanitize(expr)
        if not expression:
            return ToolResult(success=False, output="表达式为空或包含无效字符", error="invalid expression")

        precision = params.get("precision")

        try:
            result = eval(expression, {"__builtins__": {}}, self.SAFE_FUNCTIONS)
        except ZeroDivisionError:
            return ToolResult(success=False, output="除数不能为零", error="division by zero")
        except (SyntaxError, TypeError, ValueError) as e:
            return ToolResult(success=False, output=f"表达式无效: {e}", error=str(e))
        except Exception as e:
            return ToolResult(success=False, output=f"计算失败: {e}", error=str(e))

        if precision is not None:
            result = round(result, int(precision))

        return ToolResult(
            success=True,
            output=str(result),
            data={"expression": expression, "result": result, "type": type(result).__name__},
        )


class UnitConvertTool(Tool):
    """单位换算"""

    LENGTH_TO_METER = {
        "km": 1000, "m": 1, "cm": 0.01, "mm": 0.001,
        "mi": 1609.344, "ft": 0.3048, "in": 0.0254,
    }
    WEIGHT_TO_KG = {
        "kg": 1, "g": 0.001, "mg": 0.000001,
        "lb": 0.453592, "oz": 0.0283495,
    }

    def __init__(self):
        super().__init__(
            name="unit_convert",
            description="常见单位换算：长度(km/m/cm/mm/mi/ft/in)、重量(kg/g/lb/oz)、温度(C/F/K)",
            permission=ToolPermission.READ,
            parameters={
                "value": {"type": "number", "description": "要转换的数值"},
                "from": {"type": "string", "description": "源单位"},
                "to": {"type": "string", "description": "目标单位"},
                "category": {"type": "string", "description": "类别: length/weight/temperature（不填则自动检测）"},
            },
        )

    def execute(self, **params) -> ToolResult:
        value = params.get("value")
        from_unit = params.get("from", "")
        to_unit = params.get("to", "")
        category = params.get("category", "")

        if value is None:
            return ToolResult(success=False, output="未提供数值", error="empty input")

        try:
            value = float(value)
        except (TypeError, ValueError):
            return ToolResult(success=False, output=f"无效数值: {value}", error="invalid value")

        f_unit = from_unit.lower().strip()
        t_unit = to_unit.lower().strip()

        if not category:
            if f_unit in self.LENGTH_TO_METER:
                category = "length"
            elif f_unit in self.WEIGHT_TO_KG:
                category = "weight"
            elif f_unit in ("c", "f", "k", "°c", "°f", "celsius", "fahrenheit", "kelvin"):
                category = "temperature"

        if category == "temperature":
            return self._convert_temperature(value, f_unit, t_unit)
        elif category == "length":
            return self._convert_linear(value, f_unit, t_unit, self.LENGTH_TO_METER, "米")
        elif category == "weight":
            return self._convert_linear(value, f_unit, t_unit, self.WEIGHT_TO_KG, "千克")
        else:
            return ToolResult(
                success=False,
                output=f"不支持的换算类别或单位: {from_unit} → {to_unit}",
                error="unsupported category",
            )

    def _convert_linear(self, value, from_u, to_u, table, base_name):
        if from_u not in table:
            return ToolResult(success=False, output=f"不支持的源单位: {from_u}", error="invalid unit")
        if to_u not in table:
            return ToolResult(success=False, output=f"不支持的目标单位: {to_u}", error="invalid unit")

        base_value = value * table[from_u]
        result = base_value / table[to_u]

        return ToolResult(
            success=True,
            output=f"{value} {from_u} = {result:.4f} {to_u}",
            data={"value": value, "from": from_u, "to": to_u, "result": result, "base_unit": base_name},
        )

    def _convert_temperature(self, value, from_u, to_u):
        f_norm = from_u.replace("°", "").lower()
        t_norm = to_u.replace("°", "").lower()
        f_norm = {"celsius": "c", "fahrenheit": "f", "kelvin": "k"}.get(f_norm, f_norm)
        t_norm = {"celsius": "c", "fahrenheit": "f", "kelvin": "k"}.get(t_norm, t_norm)

        if f_norm == "c":
            celsius = value
        elif f_norm == "f":
            celsius = (value - 32) * 5 / 9
        elif f_norm == "k":
            celsius = value - 273.15
        else:
            return ToolResult(success=False, output=f"不支持的源温度单位: {from_u}", error="invalid unit")

        if t_norm == "c":
            result = celsius
        elif t_norm == "f":
            result = celsius * 9 / 5 + 32
        elif t_norm == "k":
            result = celsius + 273.15
        else:
            return ToolResult(success=False, output=f"不支持的目标温度单位: {to_u}", error="invalid unit")

        unit_symbols = {"c": "°C", "f": "°F", "k": "K"}

        return ToolResult(
            success=True,
            output=f"{value}{unit_symbols.get(f_norm, f_norm)} = {result:.2f}{unit_symbols.get(t_norm, t_norm)}",
            data={"value": value, "from": from_u, "to": to_u, "result": result},
        )
