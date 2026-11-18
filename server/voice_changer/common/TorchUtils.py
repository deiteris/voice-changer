import torch

def circular_write(new_data: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    offset = new_data.shape[0]
    if offset == 0 or target.shape[0] == 0:
        return target
    if offset >= target.shape[0]:
        target[:] = new_data[-target.shape[0]:]
        return target
    target[: -offset] = target[offset :].detach().clone()
    target[-offset :] = new_data
    return target
