"""Confere isolamento do perfil privilegiado e dependências das métricas."""
from pathlib import Path
import subprocess
import yaml

root = Path(__file__).resolve().parents[1]
for environment in ("desenvolvimento", "aceite", "producao"):
    rendered = subprocess.check_output(
        ["kubectl", "kustomize", str(root / "overlays" / environment)], text=True
    )
    flows = [
        obj for obj in yaml.safe_load_all(rendered)
        if obj and obj.get("kind") == "FlowCollector"
    ]
    assert len(flows) == 1, environment
    spec = flows[0]["spec"]
    agent = spec["agent"]["ebpf"]
    features = set(agent.get("features", []))
    assert "NetworkEvents" not in features, environment
    if environment == "desenvolvimento":
        assert agent.get("privileged") is True
        assert agent["sampling"] == 1
        assert features == {"PacketDrop", "DNSTracking", "FlowRTT"}
        metrics = set(spec["processor"]["metrics"]["includeList"])
        required = {
            "namespace_drop_packets_total", "namespace_ingress_packets_total",
            "node_drop_packets_total", "node_ingress_packets_total",
            "namespace_dns_flows_total", "namespace_dns_latency_seconds",
            "namespace_rtt_seconds",
        }
        assert required <= metrics, required - metrics
        assert not any(metric.startswith("netobserv_") for metric in metrics)
    else:
        assert not agent.get("privileged", False), environment
        assert not features, environment
        assert agent["sampling"] == 100, environment
    assert spec["networkPolicy"]["enable"] is True
    assert spec["loki"]["mode"] == "LokiStack"
print("PASS: isolamento de 3 perfis e dependências de diagnóstico/alertas")
