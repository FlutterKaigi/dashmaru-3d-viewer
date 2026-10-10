"""Clean animated-film surfaces without changing Dashmaru's reference palette.

Large, soft highlights describe the rounded sculpture. Smaller eye and beak
highlights separate those surfaces from the matte graphic markings. Everything
is standard glTF PBR; no baked lighting or renderer-specific texture is needed.
"""

from copy import deepcopy


def polish_materials(document):
    materials = document["materials"]
    by_prefix = {
        material["name"].split(" | ")[0]: i for i, material in enumerate(materials)
    }

    def surface(index, roughness, specular):
        material = materials[index]
        material["pbrMetallicRoughness"]["roughnessFactor"] = roughness
        material["extensions"] = {
            "KHR_materials_specular": {"specularFactor": specular}
        }
        return index

    def variant(source, name, roughness, specular):
        materials.append(deepcopy(materials[source]))
        materials[-1]["name"] = name
        return surface(len(materials) - 1, roughness, specular)

    surface(by_prefix["Body"], 0.64, 0.55)
    surface(by_prefix["Feathers and Fuji"], 0.58, 0.65)
    surface(by_prefix["Embroidered outlines"], 0.90, 0.10)
    surface(by_prefix["Snow, eyes and bib"], 0.78, 0.35)
    surface(by_prefix["Japan badge"], 0.70, 0.35)
    surface(by_prefix["Beak and feet"], 0.69, 0.55)
    eye = variant(
        by_prefix["Snow, eyes and bib"], "Eye whites | soft gloss", 0.28, 0.80
    )
    pupil = variant(
        by_prefix["Embroidered outlines"], "Pupils | gentle catchlight", 0.24, 0.60
    )
    beak = variant(by_prefix["Beak and feet"], "Beak | satin brown #634936", 0.46, 0.65)
    for mesh in document["meshes"]:
        name = mesh["name"]
        material = (
            eye
            if "eye white" in name
            else pupil
            if "pupil" in name
            else beak
            if name == "Pointed brown beak"
            else None
        )
        if material is not None:
            for primitive in mesh["primitives"]:
                primitive["material"] = material
    document["extensionsUsed"] = ["KHR_materials_specular"]
