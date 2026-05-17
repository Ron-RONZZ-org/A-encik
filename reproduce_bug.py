"""
Reproduction / verification script for A-encik issue #30.

Tests the `modifi` command's `dosiero` parameter to confirm it is accepted
as a positional argument (matching autish-legacy CLI) rather than a flag.

Usage:
    python reproduce_bug.py
"""
import os
import tempfile
from pathlib import Path
from typer.testing import CliRunner
from A_encik.cli import app

runner = CliRunner()


def make_enc_file(directory: str, name: str, content: str) -> str:
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def run_test(label: str, args: list, expect_success: bool) -> bool:
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"CMD : encik {' '.join(args)}")
    result = runner.invoke(app, args)
    status = "PASS" if (result.exit_code == 0) == expect_success else "FAIL"
    print(f"Exit: {result.exit_code}")
    safe_out = result.output[:300].encode("ascii", "backslashreplace").decode("ascii")
    print(f"Out : {safe_out!r}")
    print(f"Result: {status}")
    return status == "PASS"


def main():
    all_passed = True
    with tempfile.TemporaryDirectory() as tmp:
        # Create a source entry
        src_enc = make_enc_file(
            tmp, "source.enc",
            'terminologio.eo = "Origino"\ndifino.eo = "originala difino"\n'
        )
        repl_enc = make_enc_file(
            tmp, "replace.enc",
            'terminologio.eo = "Modifita"\ndifino.eo = "nova difino"\n'
        )

        # Add the entry
        print("\n" + "="*60)
        print("SETUP: Adding initial entry via 'aldoni'")
        result = runner.invoke(app, ["aldoni", src_enc])
        print(f"Exit: {result.exit_code}")
        print(f"Out : {result.output[:300]!r}")
        if result.exit_code != 0:
            print("ERROR: Could not create test entry. Setup failed.")
            return

        # --- Test 1: positional argument (THE FIX) ---
        ok = run_test(
            "modifi <UUID-by-title> <file.enc>  (positional — should SUCCEED)",
            ["modifi", "Origino", repl_enc],
            expect_success=True,
        )
        all_passed = all_passed and ok

        # --- Test 2: old flag form should NOT be accepted anymore ---
        ok = run_test(
            "modifi <UUID-by-title> --dosiero <file.enc>  (flag — should FAIL in new CLI)",
            ["modifi", "Origino", "--dosiero", repl_enc],
            expect_success=False,
        )
        all_passed = all_passed and ok

        # --- Test 3: -D flag should also NOT be valid ---
        ok = run_test(
            "modifi <UUID-by-title> -D <file.enc>  (-D flag — should FAIL in new CLI)",
            ["modifi", "Origino", "-D", repl_enc],
            expect_success=False,
        )
        all_passed = all_passed and ok

    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED [OK] -- positional dosiero is working correctly.")
    else:
        print("SOME TESTS FAILED [FAIL] -- see output above for details.")
    print("="*60)


if __name__ == "__main__":
    main()
