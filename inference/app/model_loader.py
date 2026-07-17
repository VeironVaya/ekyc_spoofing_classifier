import timm
import torch

# Confirmed from the training notebook: model_fold_0.pth is a raw state_dict
# (torch.save(model.state_dict(), ...)) for a ConvNeXt-Small trained via timm,
# not a full checkpoint object.
ARCHITECTURE = "convnext_small.fb_in22k_ft_in1k"
NUM_CLASSES = 6


def load_model(weights_path: str, device: str = "cpu") -> torch.nn.Module:
    model = timm.create_model(ARCHITECTURE, pretrained=False, num_classes=NUM_CLASSES)

    checkpoint = torch.load(weights_path, map_location=device, weights_only=True)
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        checkpoint = checkpoint["state_dict"]
    elif isinstance(checkpoint, dict) and "model" in checkpoint:
        checkpoint = checkpoint["model"]

    state_dict = {k.replace("module.", ""): v for k, v in checkpoint.items()}
    model.load_state_dict(state_dict)

    model.to(device)
    model.eval()
    return model
