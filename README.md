# lilToon VAT Shader

This shader is a VAT (Vertex Animation Texture) system for the lilToon.

This is a custom shader of lilToon that ports the nekoVAT system by nekoya to lilToon.

You can use original nekoVAT system by nekoya for creating VAT textures in blender, or you can use our customized texture generator in .blender directory.

nekoVAT system by nekoya: https://booth.pm/ja/items/5943052

## Usage

1. Create a VAT animation in Blender
2. Create VAT Texture (and optionally mock object) with blender plugin
4. Export & Import VAT Texture and object to Unity
   When exporting, make sure:
     - The VAT Texture is exported as a non-color RGBA exr texture
     - The object should be exported with
       Scale = FBX All, Froward = -Z Forward, Up = Y Up, and Apply Transform enabled
   When importing, make sure:
     - The VAT Texture is imported as Float RGBA texture
     - The object is imported with vertex order optimization disabled if mock object is used
5. Create a material with lilToon VAT shader
6. Assign the VAT Texture to the material, and enable mock if you use mock object

## Notes
- Because of liltoon's problem, normals transformed by VAT may not be applied for outline rendering so
  you might see weird outline artifacts, especially when using mock object mode.
  https://github.com/lilxyzw/lilToon/pull/296
