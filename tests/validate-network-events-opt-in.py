"""Garante que NetworkEvents permaneça opt-in sem modificar FeatureGate."""
from pathlib import Path
import subprocess
import yaml

root = Path(__file__).resolve().parents[1]
for profile in ("desenvolvimento", "aceite", "producao", "desenvolvimento-network-events"):
    objects = [o for o in yaml.safe_load_all(subprocess.check_output(
        ["kubectl", "kustomize", str(root / "overlays" / profile)], text=True)) if o]
    assert not any(o["kind"] == "FeatureGate" for o in objects), profile
    flows = [o for o in objects if o["kind"] == "FlowCollector"]
    assert len(flows) == 1
    agent = flows[0]["spec"]["agent"]["ebpf"]
    features = set(agent.get("features", []))
    metrics = set(flows[0]["spec"]["processor"]["metrics"]["includeList"])
    if profile == "desenvolvimento-network-events":
        assert features == {"PacketDrop", "DNSTracking", "FlowRTT", "NetworkEvents"}
        assert agent["privileged"] is True and agent["sampling"] == 1
        assert "namespace_network_policy_events_total" in metrics
    else:
        assert "NetworkEvents" not in features, profile
        assert "namespace_network_policy_events_total" not in metrics, profile
print("PASS: 4 perfis; NetworkEvents e métrica somente no opt-in; nenhuma FeatureGate")
