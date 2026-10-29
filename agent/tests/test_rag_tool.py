import os
import tempfile

from opspilot.tools.rag_tool import RepoIndex


def test_query_retrieves_the_actually_relevant_file_not_an_arbitrary_one():
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "payments.py"), "w") as f:
            f.write("def charge_credit_card(amount, currency):\n    return stripe.Charge.create(amount=amount)\n")
        with open(os.path.join(root, "animals.md"), "w") as f:
            f.write("# Giraffes\n\nGiraffes are the tallest living terrestrial animal.\n")
        with open(os.path.join(root, "weather.py"), "w") as f:
            f.write("def get_forecast(city):\n    return requests.get(f'/weather/{city}')\n")

        index = RepoIndex(root)
        results = index.query("credit card charge failed with a stripe error")

        assert results
        assert results[0].path == "payments.py"


def test_query_on_empty_repo_returns_no_results():
    with tempfile.TemporaryDirectory() as root:
        index = RepoIndex(root)
        assert index.query("anything") == []


def test_skip_dirs_are_not_indexed():
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "node_modules", "left-pad"))
        with open(os.path.join(root, "node_modules", "left-pad", "index.js"), "w") as f:
            f.write("module.exports = function leftPad() {}")
        with open(os.path.join(root, "real_code.py"), "w") as f:
            f.write("def real_function():\n    pass\n")

        index = RepoIndex(root)

        assert "real_code.py" in index._paths
        assert not any("node_modules" in p for p in index._paths)
