"""Compact Gemini response schemas; full constraints stay in Pydantic validation.

Gemini's constrained decoding rejects some valid but complex JSON schemas.
Resolve local references and omit length/range/array bounds from the wire format.
Do not relax application validation or fall back to unstructured text.
"""
from .errors import AgentError


def response_schema(model):
    document = model.model_json_schema()

    def visit(value, references=()):
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            ref = value["$ref"]
            if not ref.startswith("#/$defs/") or ref in references:
                raise AgentError("The agent output schema contains unsupported recursive references.")
            definition = document.get("$defs", {}).get(ref.removeprefix("#/$defs/"))
            if definition is None:
                raise AgentError("The agent output schema contains an unresolved reference.")
            return visit(definition, (*references, ref))
        output = {key: value[key] for key in ("type", "enum", "description", "required") if key in value}
        if "properties" in value:
            output["properties"] = {key: visit(child, references) for key, child in value["properties"].items()}
        for key in ("items", "additionalProperties"):
            if key in value:
                output[key] = visit(value[key], references)
        if "anyOf" in value:
            output["anyOf"] = [visit(child, references) for child in value["anyOf"]]
        return output

    return visit(document)
