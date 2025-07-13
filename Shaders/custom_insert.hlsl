/*
* MIT License
 * 
 * Copyright (c) 2024 nekoco (original author)
 * Copyright (c) 2025 anatawa12 (ported to liltoon custom shader)
 * 
 * Permission is hereby granted, free of charge, to any person obtaining a 
 * copy of this software and associated documentation files (the 
 * "Software"), to deal in the Software without restriction, including 
 * without limitation the rights to use, copy, modify, merge, publish, 
 * distribute, sublicense, and/or sell copies of the Software, and to 
 * permit persons to whom the Software is furnished to do so, subject to 
 * the following conditions:
 * 
 * The above copyright notice and this permission notice shall be 
 * included in all copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, 
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF 
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND 
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE 
 * LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION 
 * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION 
 * WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifdef __RESHARPER__
#define LIL_APP_NORMAL
#include "custom.hlsl"
#include "UnityShaderVariables.cginc"
#include "Packages/jp.lilxyzw.liltoon/Shader/Includes/lil_common_macro.hlsl"
#define TEXTURE2D(tex) Texture2D tex
#define SAMPLER(samp) SamplerState samp
LIL_CUSTOM_TEXTURES
LIL_CUSTOM_PROPERTIES
#endif

#define _IsMock _IsFluid

void ShortUnpack(float v, out int v1, out int v2)
{
     uint ix = asuint(v);
     v1 = (ix & 0x3FFF0000) >> 16;
     v2 = (ix & 0x00003FFF);
}

half3 NormalUnpack(float v){
     uint ix = asuint(v);
     half3 normal = half3((ix & 0x00FF0000) >> 16, (ix & 0x0000FF00) >> 8, ix & 0x000000FF);
     return normal / 255.0 * 2.0 - 1.0;
}

float rand(float2 uv)
{
     return frac(sin(dot(uv, float2(12.9898, 78.233))) * 43758.5453);
}

void compute_vat_pos_normal(uint vid, float2 uv1, float column, float motion, inout float3 positionOS, inout float4 tangentOS, inout float3 normalOS)
{
     float2 uv;
     if (_IsMock) {
          uv = float2(
              float(vid) % _PosTexture_TexelSize.z * _PosTexture_TexelSize.x,
              (int(float(vid) * _PosTexture_TexelSize.x) + 1.0f) * _PosTexture_TexelSize.y
          );
     } else {
          uv = uv1;
     }
     uv.y += _PosTexture_TexelSize.y * column * motion;

     float4 tex = LIL_SAMPLE_2D_LOD(_PosTexture, anatawa12_vat_sampler_point_repeat, uv, 0);
     float3 pos = float3(tex.r, tex.b, tex.g);
     half3 normal = NormalUnpack(tex.a);
     normal = normalize(half3(normal.x, normal.z, normal.y));

     if (_IsSkinningMode) {
          float3 bitangentOS = normalize(cross(normalOS, tangentOS.xyz)) * (tangentOS.w * length(normalOS));
          float3x3 tbnOS = float3x3(tangentOS.xyz, normalOS, bitangentOS);

          positionOS += mul(tbnOS, pos);
          normalOS = normalize(mul(tbnOS, normal));

          // rotate tangentOS as like rotating (0,0,1) to normal
          float3 xaxis = normalize(cross(float3(0,0,1), normal));
          float3 yaxis = normalize(cross(normal, xaxis));
          float3x3 normalRotation = float3x3(xaxis, normal, yaxis);
          tangentOS.xyz = normalize(mul(normalRotation, tangentOS.xyz));
     } else {
          positionOS = pos;
          normalOS = normal;
     }
}

void vat_fragment(uint vid, in float2 uv1, inout float3 normalOS, inout float4 tangentOS, inout float4 positionOS)
{
     float4 param = LIL_SAMPLE_2D_LOD(_PosTexture, anatawa12_vat_sampler_point_repeat, 0, 0);
     int column, maxMotion;
     ShortUnpack(param.r, column, maxMotion);

     float motion;
     if (_TimeMotion) {
          motion = _Time.y *_FPS;
     } else {
          motion = _Motion;
     }
     if (_IsRand) {
          float4 wpos_object = mul(unity_ObjectToWorld, float4(0.0f, 0.0f, 0.0f, 1.0f));
          motion += rand(float2(rand(float2(wpos_object.x, wpos_object.y)), wpos_object.z)) * maxMotion;
     }
     motion = motion % maxMotion;

     float3 pos = positionOS;
     float3 normal = normalOS;
     float4 tangent = tangentOS;
     compute_vat_pos_normal(vid, uv1, column, floor(motion), pos, tangent, normal);

     if (_IsLerp) {
          float3 pos2 = positionOS;
          float3 normal2 = normalOS;
          float4 tangent2 = tangentOS;
          compute_vat_pos_normal(vid, uv1, column, (motion >= maxMotion - 1.0f) ? 0 : ceil(motion), pos2, tangent2, normal2);

          pos = lerp(pos, pos2, frac(motion));
          normal = lerp(normal, normal2, frac(motion));
          tangent = lerp(tangent, tangent2, frac(motion));
     }

     positionOS.xyz = pos;
     normalOS = normal;
     tangentOS = tangent;
}

