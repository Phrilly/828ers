import os

# The file where all your code will be dumped
output_file = 'golf_codebase_context.txt'

# The file types you want me to read
allowed_extensions = ['.php', '.css', '.js', '.py']

# Folders to ignore (like vendor files, virtual environments, or node_modules)
ignore_dirs = ['node_modules', 'vendor', '.git', '__pycache__', 'venv']

with open(output_file, 'w', encoding='utf-8') as outfile:
    for subdir, dirs, files in os.walk('.'):
        # Remove ignored directories from the walk
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if any(file.endswith(ext) for ext in allowed_extensions):
                # Skip the bundler script itself
                if file == 'bundle_code.py':
                    continue
                    
                filepath = os.path.join(subdir, file)
                outfile.write(f"\n\n{'='*50}\n")
                outfile.write(f"FILE: {filepath}\n")
                outfile.write(f"{'='*50}\n\n")
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"[Error reading file: {e}]\n")

print(f"Codebase bundled successfully into {output_file}")