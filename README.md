# Boolean Expression Optimizer & Circuit Simulator Pro

A beginner-friendly Boolean logic web app that:
- Simplifies Boolean expressions
- Generates a truth table
- Checks equivalence of original and optimized expressions
- Generates Verilog modules and a testbench
- Runs Icarus Verilog simulation when available

## Supported input
Variables `A` through `F`; operators `&` (AND), `|` (OR), `~` (NOT), parentheses, and constants `0` and `1`.

Example:
`(A & B) | (A & ~B)`

## Run locally with Docker
```bash
docker build -t boolean-optimizer-pro .
docker run --rm -p 7860:7860 boolean-optimizer-pro
```
Open http://localhost:7860.

## Deploy to Render
1. Push this folder to a new GitHub repository.
2. In Render, choose **New + → Web Service** and connect the repository.
3. Choose **Docker** as the runtime/environment.
4. Create the service and wait for the build to finish.
5. Open the Render URL.

The Docker image installs Icarus Verilog and starts the Gradio app on Render's `PORT`.

## Current scope
This starter deployment includes the optimizer, truth table, Verilog, testbench, and simulation output. Circuit schematic diagrams, waveform plots, K-maps, and downloadable reports can be added in later iterations.
