import tomlkit

with open("pyproject.toml", "r") as f:
    data = tomlkit.load(f)

if "project" in data and "dependencies" in data["project"]:
    new_deps = []
    for dep in data["project"]["dependencies"]:
        new_deps.append(dep.split(">=")[0])
    data["project"]["dependencies"] = new_deps

if "project" in data and "optional-dependencies" in data["project"]:
    for group in data["project"]["optional-dependencies"]:
        new_deps = []
        for dep in data["project"]["optional-dependencies"][group]:
            new_deps.append(dep.split(">=")[0].split("==")[0])
        data["project"]["optional-dependencies"][group] = new_deps

with open("pyproject.toml", "w") as f:
    tomlkit.dump(data, f)
