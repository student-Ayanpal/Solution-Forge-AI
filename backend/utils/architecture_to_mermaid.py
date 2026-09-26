from backend.models.solution_architecture import SolutionArchitecture


def architecture_to_mermaid(architecture: SolutionArchitecture) -> str:

    lines = [
        "flowchart TD"
    ]

    for component in architecture.components:

        component_id = component.id
        name = component.name.replace('"', "'")

        lines.append(
            f'    {component_id}["{name}"]'
        )

    # Add database
    lines.append(
        '    database[("Primary Database")]'
    )

    # Add cache
    if architecture.cache.required:
        lines.append(
            '    cache[("Cache")]'
        )

    # Add component connections
    for connection in architecture.connections:

        source = connection.source
        target = connection.target

        if connection.label:
            label = connection.label.replace('"', "'")

            lines.append(
                f'    {source} -->|{label}| {target}'
            )
        else:
            lines.append(
                f'    {source} --> {target}'
            )

    return "\n".join(lines)