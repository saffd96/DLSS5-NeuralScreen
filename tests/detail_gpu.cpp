// Run the production detail shader on WARP; --bench times copy + shader
// on the default hardware adapter. Pixel assertions use GPU readback.
#define NOMINMAX
#include <windows.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <DirectXPackedVector.h>
#include <array>
#include <vector>
#include <cstdio>
#include <cmath>
#include <stdexcept>
#include <cstring>
#include <algorithm>
#include "../native/detail_shaders.h"

using Microsoft::WRL::ComPtr;
using namespace DirectX::PackedVector;
static UINT W = 17, H = 9; // also exercises dispatch bounds
using Pixel = std::array<float, 4>;
static ComPtr<ID3D11Device> dev;
static ComPtr<ID3D11DeviceContext> ctx;
static void check(bool ok, const char *what) { if (!ok) throw std::runtime_error(what); }
static void hr(HRESULT v) { check(SUCCEEDED(v), "Direct3D call failed"); }
static ComPtr<ID3D11Texture2D> texture(DXGI_FORMAT fmt, const void *data, UINT bpp, bool output=false)
{
    D3D11_TEXTURE2D_DESC d = {};
    d.Width=W; d.Height=H; d.MipLevels=1; d.ArraySize=1; d.Format=fmt; d.SampleDesc.Count=1;
    d.BindFlags=D3D11_BIND_SHADER_RESOURCE | (output ? D3D11_BIND_UNORDERED_ACCESS : 0);
    D3D11_SUBRESOURCE_DATA init={data,W*bpp,0};
    ComPtr<ID3D11Texture2D> t; hr(dev->CreateTexture2D(&d,data ? &init : nullptr,&t)); return t;
}
static std::vector<unsigned char> read(ID3D11Texture2D *t, UINT bpp)
{
    D3D11_TEXTURE2D_DESC d; t->GetDesc(&d); d.BindFlags=0;
    d.Usage=D3D11_USAGE_STAGING; d.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    ComPtr<ID3D11Texture2D> staging; hr(dev->CreateTexture2D(&d,nullptr,&staging));
    ctx->CopyResource(staging.Get(),t);
    D3D11_MAPPED_SUBRESOURCE m; hr(ctx->Map(staging.Get(),0,D3D11_MAP_READ,0,&m));
    std::vector<unsigned char> bytes(W*H*bpp);
    for(UINT y=0;y<H;++y) memcpy(bytes.data()+y*W*bpp,(char*)m.pData+y*m.RowPitch,W*bpp);
    ctx->Unmap(staging.Get(),0); return bytes;
}
static void dispatch(const char *shader, std::vector<ID3D11Texture2D*> inputs,
                     ID3D11Texture2D *out, const void *constants, double *timing=nullptr, ID3D11Texture2D *original=nullptr)
{
    ComPtr<ID3DBlob> code,errors;
    HRESULT result=D3DCompile(shader,strlen(shader),"hdr-test",nullptr,nullptr,"main","cs_5_0",
                             D3DCOMPILE_WARNINGS_ARE_ERRORS,0,&code,&errors);
    if(FAILED(result) && errors) fprintf(stderr,"%s\n",(char*)errors->GetBufferPointer());
    hr(result);
    ComPtr<ID3D11ComputeShader> cs; hr(dev->CreateComputeShader(code->GetBufferPointer(),code->GetBufferSize(),nullptr,&cs));
    std::vector<ComPtr<ID3D11ShaderResourceView>> views(inputs.size());
    std::vector<ID3D11ShaderResourceView*> ptrs;
    for(size_t i=0;i<inputs.size();++i) { hr(dev->CreateShaderResourceView(inputs[i],nullptr,&views[i])); ptrs.push_back(views[i].Get()); }
    ComPtr<ID3D11UnorderedAccessView> uav; hr(dev->CreateUnorderedAccessView(out,nullptr,&uav));
    D3D11_BUFFER_DESC bd={}; bd.ByteWidth=16; bd.Usage=D3D11_USAGE_DEFAULT; bd.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
    D3D11_SUBRESOURCE_DATA data={constants,0,0}; ComPtr<ID3D11Buffer> cb; hr(dev->CreateBuffer(&bd,&data,&cb));
    ctx->CSSetShader(cs.Get(),nullptr,0); ctx->CSSetConstantBuffers(0,1,cb.GetAddressOf());
    ctx->CSSetShaderResources(0,(UINT)ptrs.size(),ptrs.data());
    ctx->CSSetUnorderedAccessViews(0,1,uav.GetAddressOf(),nullptr);
    ComPtr<ID3D11Query> qa,qb,qd;
    if(timing) {
        D3D11_QUERY_DESC desc={D3D11_QUERY_TIMESTAMP,0};
        hr(dev->CreateQuery(&desc,&qa));hr(dev->CreateQuery(&desc,&qb));
        desc.Query=D3D11_QUERY_TIMESTAMP_DISJOINT;hr(dev->CreateQuery(&desc,&qd));
        ctx->Begin(qd.Get());ctx->End(qa.Get());
    }
    if(original)ctx->CopyResource(inputs[0],original);
    ctx->Dispatch((W+7)/8,(H+7)/8,1);
    if(timing) {
        ctx->End(qb.Get());ctx->End(qd.Get());ctx->Flush();
        D3D11_QUERY_DATA_TIMESTAMP_DISJOINT d{};
        ULONGLONG deadline=GetTickCount64()+10000;
        while(ctx->GetData(qd.Get(),&d,sizeof(d),0)==S_FALSE) {check(GetTickCount64()<deadline,"timestamp timeout");Sleep(1);}
        UINT64 a=0,b=0;hr(ctx->GetData(qa.Get(),&a,sizeof(a),0));hr(ctx->GetData(qb.Get(),&b,sizeof(b),0));
        check(!d.Disjoint && d.Frequency && b>=a,"invalid GPU timestamps");
        *timing=double(b-a)*1000.0/d.Frequency;
    }

    ctx->ClearState();
}
int main(int argc, char**) {
 try {
  D3D_FEATURE_LEVEL fl=D3D_FEATURE_LEVEL_11_0;
  bool bench=argc>1;
  if(bench){W=2560;H=1440;}
  hr(D3D11CreateDevice(nullptr,bench?D3D_DRIVER_TYPE_HARDWARE:D3D_DRIVER_TYPE_WARP,nullptr,0,&fl,1,D3D11_SDK_VERSION,&dev,nullptr,&ctx));
  std::vector<unsigned char> pixels(W*H*4);
  for(UINT y=0;y<H;++y)for(UINT x=0;x<W;++x) {
   UINT i=(y*W+x)*4;
   unsigned char levels[]={20,20,25,55,120,190,215,220,220};
   for(UINT c=0;c<3;++c)pixels[i+c]=levels[x%9];
   pixels[i+3]=(unsigned char)(30+y*20);
  }
  auto input=texture(DXGI_FORMAT_R8G8B8A8_UNORM,pixels.data(),4);
  auto output=texture(DXGI_FORMAT_R8G8B8A8_UNORM,nullptr,4,true);
  struct {UINT w,h;float strength,pad;} params={W,H,0,0};
  if(bench) {
   auto original=texture(DXGI_FORMAT_R8G8B8A8_UNORM,pixels.data(),4);
   params.strength=.5f;std::vector<double> times;
   for(int i=0;i<30;++i){double ms=0;dispatch(kDetailHlsl,{input.Get()},output.Get(),&params,&ms,original.Get());if(i>=5)times.push_back(ms);}
   std::sort(times.begin(),times.end());
   printf("GPU copy + detail shader 2560x1440: median %.4f ms, min %.4f, max %.4f\n",times[12],times.front(),times.back());
   return 0;
  }
  dispatch(kDetailHlsl,{input.Get()},output.Get(),&params);
  check(read(output.Get(),4)==pixels,"zero strength changed pixels");
  params.strength=1;
  dispatch(kDetailHlsl,{input.Get()},output.Get(),&params);
  auto enhanced=read(output.Get(),4);unsigned changed=0;
  for(UINT y=0;y<H;++y)for(UINT x=0;x<W;++x) {
   UINT i=(y*W+x)*4;
   check(enhanced[i+3]==pixels[i+3],"alpha changed");
   for(UINT c=0;c<3;++c) {
    int low=pixels[i+c],high=low;
    const UINT neighbours[]={y*W+(x?x-1:x),y*W+(x+1<W?x+1:x),(y?y-1:y)*W+x,(y+1<H?y+1:y)*W+x,
      y*W+(x>1?x-2:0),y*W+(std::min)(x+2,W-1),(y>1?y-2:0)*W+x,(std::min)(y+2,H-1)*W+x};
    for(auto n:neighbours){low=(std::min)(low,int(pixels[n*4+c]));high=(std::max)(high,int(pixels[n*4+c]));}
    check(enhanced[i+c]>=low && enhanced[i+c]<=high,"overshoot beyond neighbours");
    check(abs(int(enhanced[i+c])-pixels[i+c])<=31,"excessive change");
    changed+=enhanced[i+c]!=pixels[i+c];
   }
  }
  check(changed>0,"positive strength has no effect");
  // A soft, low-contrast edge: the previous contrast-gated kernel rounded
  // to no change here. Require a visible response and monotonic control.
  for(UINT y=0;y<H;++y)for(UINT x=0;x<W;++x) {
   unsigned char levels[]={100,100,101,104,110,116,119,120,120};
   for(UINT c=0;c<3;++c)pixels[(y*W+x)*4+c]=levels[x%9];
  }
  input=texture(DXGI_FORMAT_R8G8B8A8_UNORM,pixels.data(),4);
  params.strength=.5f;dispatch(kDetailHlsl,{input.Get()},output.Get(),&params);
  auto half=read(output.Get(),4);
  params.strength=1;dispatch(kDetailHlsl,{input.Get()},output.Get(),&params);
  auto full=read(output.Get(),4);
  int halfEffect=0,fullEffect=0;
  for(UINT i=0;i<W*H*4;i+=4) {
   int a=abs(int(half[i])-pixels[i]),b=abs(int(full[i])-pixels[i]);
   check(b>=a,"slider response is not monotonic");
   halfEffect=(std::max)(halfEffect,a);fullEffect=(std::max)(fullEffect,b);
  }
  check(halfEffect>=1 && fullEffect>=3 && fullEffect>halfEffect,"soft detail suppressed");
  params.strength=2;dispatch(kDetailHlsl,{input.Get()},output.Get(),&params);
  auto twice=read(output.Get(),4);
  check(twice==full,"out-of-range strength must clamp to 100%");
  for(UINT i=0;i<W*H*4;i+=4) {
   check(abs(int(twice[i])-pixels[i])>=abs(int(full[i])-pixels[i]),"200% weakened effect");
   check(abs(int(twice[i])-pixels[i])<=31,"200% exceeded bounds");
   check(twice[i+3]==pixels[i+3],"200% changed alpha");
  }
  params.strength=0;dispatch(kDetailHlsl,{input.Get()},output.Get(),&params);
  check(read(output.Get(),4)==pixels,"returning to zero changed pixels");
  std::fill(pixels.begin(),pixels.end(),static_cast<unsigned char>(100));
  params.strength=2;
  input=texture(DXGI_FORMAT_R8G8B8A8_UNORM,pixels.data(),4);
  dispatch(kDetailHlsl,{input.Get()},output.Get(),&params);
  check(read(output.Get(),4)==pixels,"flat area changed");
  printf("PASS: production detail shader: zero identity, flat identity, alpha, bounds and effect\n");
  return 0;
 } catch(const std::exception &e) { fprintf(stderr,"FAIL: %s\n",e.what());return 1; }
}
