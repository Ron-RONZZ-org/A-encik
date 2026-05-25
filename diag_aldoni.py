"""Quick diagnostic to check aldoni works."""
import tempfile
import os
import traceback

from typer.testing import CliRunner
from A_encik.cli import app

runner = CliRunner()

with tempfile.TemporaryDirectory() as tmp:
    src = os.path.join(tmp, "test.enc")
    with open(src, "w", encoding="utf-8") as f:
        f.write('terminologio.eo = "Testa"\ndifino.eo = "testa difino"\n')

    r = runner.invoke(app, ["aldoni", src])
    print("Exit:", r.exit_code)
    print("Output:", r.output)
    if r.exception:
        traceback.print_exception(type(r.exception), r.exception, r.exception.__traceback__)
