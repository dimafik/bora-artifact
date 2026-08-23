import sys
sys.path.insert(0, "/mnt/d/fabric-d2/alg1")
# Import only the config-loading bit
exec(compile(
    open("/mnt/d/fabric-d2/alg1/sidecar.py").read().split("def main():")[0]
        .replace("if __name__", "if False and __name__"),
    "sidecar_loader", "exec"))
cfg = load_config("/mnt/d/fabric-d2/alg1/alg1.yaml")
import json
print(json.dumps(cfg, indent=2))
