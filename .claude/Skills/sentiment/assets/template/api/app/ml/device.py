"""Pick the torch device to run models on."""

import torch


def resolve_device(preference: str = "auto") -> torch.device:
    cuda = torch.cuda.is_available()
    mps = bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available()
    if preference == "cpu":
        return torch.device("cpu")
    if preference == "cuda":
        if not cuda:
            raise RuntimeError("DEVICE=cuda but no CUDA GPU is available to PyTorch")
        return torch.device("cuda")
    if preference == "mps":
        if not mps:
            raise RuntimeError("DEVICE=mps but Apple Metal (MPS) is not available to PyTorch")
        return torch.device("mps")
    if cuda:
        return torch.device("cuda")
    if mps:
        return torch.device("mps")
    return torch.device("cpu")


def describe_device(device: torch.device) -> str:
    if device.type == "cuda":
        index = device.index if device.index is not None else torch.cuda.current_device()
        return f"cuda:{index} ({torch.cuda.get_device_name(index)})"
    return device.type
