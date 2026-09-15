#pragma once
// Spatial detail enhancement, not reconstruction of missing information.
static const char kDetailHlsl[] = R"hlsl(
Texture2D<float4> Source : register(t0);
RWTexture2D<float4> Target : register(u0);
cbuffer Params : register(b0) { uint Width, Height; float Strength; };
[numthreads(8,8,1)] void main(uint3 tid : SV_DispatchThreadID) {
    if (tid.x >= Width || tid.y >= Height) return;
    int2 p = int2(tid.xy), hi = int2(Width-1, Height-1);
    float4 c = Source.Load(int3(p,0));
    float3 n = Source.Load(int3(clamp(p+int2(0,-1),0,hi),0)).rgb;
    float3 s = Source.Load(int3(clamp(p+int2(0,1),0,hi),0)).rgb;
    float3 e = Source.Load(int3(clamp(p+int2(1,0),0,hi),0)).rgb;
    float3 w = Source.Load(int3(clamp(p+int2(-1,0),0,hi),0)).rgb;
    float3 low = min(c.rgb,min(min(n,s),min(e,w)));
    float3 high = max(c.rgb,max(max(n,s),max(e,w)));
    float contrast = dot(high-low,float3(.2126,.7152,.0722));
    float gain = saturate(Strength)*.6*saturate((contrast-.01)/.08);
    float3 delta = clamp((c.rgb-(n+s+e+w)*.25)*gain,-.06,.06);
    Target[p] = float4(clamp(c.rgb+delta,low,high),c.a);
}
)hlsl";
