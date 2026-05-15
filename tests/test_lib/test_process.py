import pathlib

from lib.process import run


class TestRun:
    def test_returns_exit_code_zero_on_success(self):
        # 使用 python 命令代替 echo，以保证跨平台兼容性
        code = run(["python", "-c", "print('hello')"])
        assert code == 0

    def test_returns_nonzero_on_failure(self):
        code = run(["cmd", "/c", "exit", "1"])
        assert code != 0

    def test_cwd_parameter(self, tmp_dir):
        marker = tmp_dir / "marker.txt"
        marker.write_text("found", encoding="utf-8")
        code = run(["cmd", "/c", "type", "marker.txt"], cwd=str(tmp_dir))
        assert code == 0

    def test_env_parameter(self):
        import os
        custom_env = {**os.environ, "TOOLBOX_TEST_VAR": "hello123"}
        code = run(["cmd", "/c", "echo", "%TOOLBOX_TEST_VAR%"], env=custom_env)
        assert code == 0
