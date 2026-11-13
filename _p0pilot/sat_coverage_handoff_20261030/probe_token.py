import subprocess, pathlib, sys
out = pathlib.Path(sys.argv[1])
o = subprocess.run(['whoami', '/groups', '/fo', 'csv'], capture_output=True).stdout
text = o.decode('gbk', errors='replace')
out.write_text(text, encoding='utf-8')
print('ok', sys.executable)
