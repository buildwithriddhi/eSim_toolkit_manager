import subprocess

result=subprocess.run(["python", "--version"],capture_output=True,text=True,stdin=subprocess.DEVNULL)
print(result.stdout)