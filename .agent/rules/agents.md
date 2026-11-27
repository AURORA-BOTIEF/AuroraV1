# Agent Instructions

## AWS Configuration

Always use the `Netec` AWS CLI profile for any AWS-related commands in this repository. 

The environment is configured to automatically use this profile via `.envrc` (setting `AWS_PROFILE=Netec`).

If you need to specify it manually, use suffix: `--profile Netec`.

## Deployment & Architecture

### Backend Deployment
This project uses **AWS SAM** for backend deployment.
- **Command:** `sam build && sam deploy` inside `CG-Backend/`.
- **Do NOT** use `sam deploy` without building, as this will fail to update the dependency layers.
- **Do NOT** use manual zip uploads for functions defined with `AWS::Serverless::LayerVersion`.

### Dependency Management
Dependencies are managed via Lambda Layers defined in `template.yaml`. We use `AWS::Serverless::LayerVersion` with `BuildMethod: python3.12` to allow SAM to automatically build these layers from `requirements.txt`:

| Layer | Dependencies | Source |
|-------|--------------|--------|
| **PdfLayer** | `xhtml2pdf`, `jinja2` | `CG-Backend/lambda-layers/pdf_layer/requirements.txt` |
| **PPTLayer** | `python-pptx`, `Pillow` | `CG-Backend/lambda-layers/ppt_layer/requirements.txt` |
| **StrandsAgentsLayer** | Shared SDK | `CG-Backend/lambda-layers/strands_layer/` |

**To add a dependency:**
1. Update the corresponding `requirements.txt`.
2. Run `sam build && sam deploy`.
