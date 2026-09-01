import re

with open(r"android\app\src\main\java\com\example\pineal\engine\gemini\GeminiClient.kt", "r", encoding="utf-8") as f:
    content = f.read()

# Add import Header if missing
if "import retrofit2.http.Header" not in content:
    content = content.replace("import retrofit2.http.Query", "import retrofit2.http.Query\nimport retrofit2.http.Header")

# Replace @Query("key") with @Header("x-goog-api-key")
content = content.replace('@Query("key")', '@Header("x-goog-api-key")')

with open(r"android\app\src\main\java\com\example\pineal\engine\gemini\GeminiClient.kt", "w", encoding="utf-8") as f:
    f.write(content)
print("Android API Key fixed!")
