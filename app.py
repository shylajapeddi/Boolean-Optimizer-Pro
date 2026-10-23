import itertools
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import gradio as gr
import pandas as pd
import sympy as sp
from sympy.logic.boolalg import simplify_logic


def build_boolean_engine(expression):
    if not expression or len(expression) > 200:
        raise ValueError("Enter a non-empty expression under 200 characters.")

    expression = expression.strip().upper()
    if not re.fullmatch(r"[A-F01\s&|~()]+", expression):
        raise ValueError("Use variables A-F, constants 0/1, &, |, ~, and parentheses only.")

    names = sorted(set(re.findall(r"[A-F]", expression)))
    if not names:
        raise ValueError("Include at least one variable from A to F.")

    symbols = {name: sp.Symbol(name) for name in names}
    try:
        original = sp.sympify(expression, locals=symbols)
    except Exception as exc:
        raise ValueError("Invalid Boolean expression. Check operators and parentheses.") from exc

    if original.free_symbols - set(symbols.values()):
        raise ValueError("Unsupported variable in expression.")

    variables = [symbols[name] for name in names]
    optimized = simplify_logic(original, form="dnf", force=True)

    rows = []
    equivalent = True
    for values in itertools.product([0, 1], repeat=len(variables)):
        assignment = {var: bool(value) for var, value in zip(variables, values)}
        original_out = int(bool(original.subs(assignment)))
        optimized_out = int(bool(optimized.subs(assignment)))
        equivalent &= original_out == optimized_out
        row = dict(zip(names, values))
        row["Original F"] = original_out
        row["Optimized F"] = optimized_out
        rows.append(row)

    return {
        "original": original,
        "optimized": optimized,
        "variables": names,
        "truth_table": rows,
        "equivalent": bool(equivalent),
    }


def verilog_expr(expr):
    if expr == sp.true:
        return "1'b1"
    if expr == sp.false:
        return "1'b0"
    if isinstance(expr, sp.Symbol):
        return str(expr)
    if expr.func == sp.Not:
        return f"~({verilog_expr(expr.args[0])})"
    if expr.func == sp.And:
        return "(" + " & ".join(verilog_expr(arg) for arg in expr.args) + ")"
    if expr.func == sp.Or:
        return "(" + " | ".join(verilog_expr(arg) for arg in expr.args) + ")"
    raise ValueError(f"Unsupported Boolean expression node: {expr}")


def generate_verilog(result):
    variables = result["variables"]
    ports = ", ".join(variables + ["F"])
    declarations = ", ".join(variables)
    original_expr = verilog_expr(result["original"])
    optimized_expr = verilog_expr(result["optimized"])
    return f"""// Boolean Expression Optimizer & Circuit Simulator Pro

module original_circuit({ports});
    input {declarations};
    output F;
    assign F = {original_expr};
endmodule

module optimized_circuit({ports});
    input {declarations};
    output F;
    assign F = {optimized_expr};
endmodule
"""


def generate_testbench(result):
    variables = result["variables"]
    n = len(variables)
    declarations = "\n".join(f"    reg {v};" for v in variables)
    assigns = "\n".join(
        f"            {v} = (i >> {n - 1 - idx}) & 1;"
        for idx, v in enumerate(variables)
    )
    original_connections = ", ".join(
        [f".{v}({v})" for v in variables] + [".F(original_F)"]
    )
    optimized_connections = ", ".join(
        [f".{v}({v})" for v in variables] + [".F(optimized_F)"]
    )
    return f"""`timescale 1ns/1ps
module testbench;
{declarations}
    wire original_F;
    wire optimized_F;
    integer i;

    original_circuit original_dut({original_connections});
    optimized_circuit optimized_dut({optimized_connections});

    initial begin
        $display("Test | Inputs | Original | Optimized | Result");
        for (i = 0; i < {2 ** n}; i = i + 1) begin
{assigns}
            #1;
            if (original_F === optimized_F)
                $display("%0d | %b | %b | %b | PASS", i, {{{', '.join(variables)}}}, original_F, optimized_F);
            else
                $display("%0d | %b | %b | %b | FAIL", i, {{{', '.join(variables)}}}, original_F, optimized_F);
        end
        $finish;
    end
endmodule
"""


def run_optimizer(expression):
    try:
        result = build_boolean_engine(expression)
        table = pd.DataFrame(result["truth_table"])
        verilog = generate_verilog(result)
        testbench = generate_testbench(result)

        if shutil.which("iverilog") and shutil.which("vvp"):
            with tempfile.TemporaryDirectory() as folder:
                folder = Path(folder)
                (folder / "circuits.v").write_text(verilog)
                (folder / "testbench.v").write_text(testbench)
                compiled = subprocess.run(
                    ["iverilog", "-g2012", "-o", str(folder / "sim.out"),
                     str(folder / "circuits.v"), str(folder / "testbench.v")],
                    capture_output=True, text=True, timeout=20
                )
                if compiled.returncode != 0:
                    simulation = "Compilation FAILED\n" + compiled.stderr
                else:
                    simulated = subprocess.run(
                        ["vvp", str(folder / "sim.out")],
                        capture_output=True, text=True, timeout=20
                    )
                    simulation = simulated.stdout
                    if simulated.returncode != 0:
                        simulation += "\nSimulation process returned an error."
        else:
            simulation = "Icarus Verilog is unavailable. Boolean simplification still completed."

        status = "PASS" if result["equivalent"] else "FAIL"
        return (
            str(result["original"]),
            str(result["optimized"]),
            status,
            table,
            verilog,
            testbench,
            simulation,
        )
    except Exception as exc:
        raise gr.Error(str(exc))


with gr.Blocks(title="Boolean Optimizer Pro") as demo:
    gr.Markdown(
        "# Boolean Expression Optimizer & Circuit Simulator Pro\n"
        "Simplify Boolean logic, inspect the truth table, generate Verilog and "
        "a testbench, and simulate the circuits when Icarus Verilog is available.\n\n"
        "**Operators:** `&` AND · `|` OR · `~` NOT · parentheses for grouping. "
        "Variables: A–F."
    )
    expression = gr.Textbox(
        label="Boolean expression",
        value="(A & B) | (A & ~B)",
        placeholder="Example: (A & B) | (A & ~B)",
        lines=2,
    )
    run_button = gr.Button("Optimize and Verify", variant="primary")
    with gr.Row():
        original_output = gr.Textbox(label="Original expression")
        optimized_output = gr.Textbox(label="Optimized expression")
        equivalence_output = gr.Textbox(label="Boolean equivalence")
    truth_table = gr.Dataframe(label="Truth table", interactive=False)
    verilog_output = gr.Code(label="Generated Verilog", language="python", interactive=False)
    testbench_output = gr.Code(label="Generated testbench", language="python", interactive=False)
    simulation_output = gr.Textbox(label="Icarus Verilog simulation output", lines=12, interactive=False)

    run_button.click(
        run_optimizer,
        inputs=[expression],
        outputs=[
            original_output, optimized_output, equivalence_output,
            truth_table, verilog_output, testbench_output, simulation_output
        ],
    )

port = int(os.environ.get("PORT", "7860"))
demo.launch(server_name="0.0.0.0", server_port=port, share=False)
