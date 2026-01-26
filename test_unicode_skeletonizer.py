
from llmc.rag.skeleton import Skeletonizer

# Create a python file with unicode characters
file_content = """
# -*- coding: utf-8 -*-

def hello_world_こんにちは世界():
    '''
    A function with a unicode name and docstring.
    🎉🍕🚀
    '''
    pass

# A comment with unicode: こんにちは世界
print("Hello, world!")
"""

file_path = "unicode_test_file.py"
with open(file_path, "w", encoding="utf-8") as f:
    f.write(file_content)

# Now, let's test the skeletonizer
try:
    with open(file_path, "rb") as f:
        source = f.read()
    
    skeleton = Skeletonizer(source, lang="python").skeletonize()
    
    print("Skeleton output:")
    print(skeleton)
    
    # Check if the unicode characters are preserved
    if "こんにちは世界" in skeleton and "🎉🍕🚀" in skeleton:
        print("Unicode characters are preserved in skeleton.")
    else:
        print("Unicode characters are NOT preserved in skeleton.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    import os
    os.remove(file_path)
    if os.path.exists("test_skeletonizer.py"):
        os.remove("test_skeletonizer.py")
