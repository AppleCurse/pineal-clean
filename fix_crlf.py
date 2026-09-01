with open("scripts/test_disaster_recovery.sh", "rb") as f:
    content = f.read()
content = content.replace(b"\r\n", b"\n")
with open("scripts/test_disaster_recovery.sh", "wb") as f:
    f.write(content)
