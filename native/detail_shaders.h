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
    float3 n2 = Source.Load(int3(clamp(p+int2(0,-2),0,hi),0)).rgb;
    float3 s2 = Source.Load(int3(clamp(p+int2(0,2),0,hi),0)).rgb;
    float3 e2 = Source.Load(int3(clamp(p+int2(2,0),0,hi),0)).rgb;
    float3 w2 = Source.Load(int3(clamp(p+int2(-2,0),0,hi),0)).rgb;
    float3 low = min(c.rgb,min(min(min(n,s),min(e,w)),min(min(n2,s2),min(e2,w2))));
    float3 high = max(c.rgb,max(max(max(n,s),max(e,w)),max(max(n2,s2),max(e2,w2))));
    // A wider footprint reaches across a soft edge. The old one-pixel
    // kernel plus contrast gate suppressed precisely those blurry details.
    float3 blur = (n+s+e+w)*.125 + (n2+s2+e2+w2)*.125;
    float3 residual = c.rgb-blur;
    // Soft noise floor (half an 8-bit level), then a 0..3 gain (0..100%).
    residual = sign(residual)*max(abs(residual)-.002,0);
    float3 delta = clamp(residual*(3*saturate(Strength)),-.12,.12);
    Target[p] = float4(clamp(c.rgb+delta,low,high),c.a);
}
)hlsl";
