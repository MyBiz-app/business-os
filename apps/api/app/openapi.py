"""Prints the OpenAPI schema. The TypeScript client in packages/api-client is generated from it."""

import json
import sys

from app.main import create_app

if __name__ == "__main__":
    json.dump(create_app().openapi(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
