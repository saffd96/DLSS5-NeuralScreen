#include "detail_shaders.h"

static unsigned g_detail_strength = 0;
static struct DetailState {
    winrt::com_ptr<ID3D12Resource> input;
    winrt::com_ptr<ID3D12RootSignature> root;
    winrt::com_ptr<ID3D12PipelineState> pipeline;
    winrt::com_ptr<ID3D12DescriptorHeap> heap;
    ID3D12Resource *output = nullptr;
} g_detail;

static void CloseDetailResources()
{
    g_detail.input = nullptr;
    g_detail.heap = nullptr;
    g_detail.output = nullptr;
}

static bool EnsureDetail(VideoState &v)
{
    auto &d = g_detail;
    if (!d.pipeline) {
        D3D12_DESCRIPTOR_RANGE ranges[] = {
            {D3D12_DESCRIPTOR_RANGE_TYPE_SRV,1,0,0,0},
            {D3D12_DESCRIPTOR_RANGE_TYPE_UAV,1,0,0,1}};
        D3D12_ROOT_PARAMETER roots[2] = {};
        roots[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
        roots[0].Constants = {0,0,3};
        roots[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
        roots[1].DescriptorTable = {2,ranges};
        D3D12_ROOT_SIGNATURE_DESC rd = {2,roots,0,nullptr,D3D12_ROOT_SIGNATURE_FLAG_NONE};
        winrt::com_ptr<ID3DBlob> code, errors;
        if (FAILED(D3D12SerializeRootSignature(&rd,D3D_ROOT_SIGNATURE_VERSION_1,code.put(),errors.put())) ||
            FAILED(h.dev->CreateRootSignature(0,code->GetBufferPointer(),code->GetBufferSize(),IID_PPV_ARGS(d.root.put())))) return false;
        code=nullptr;errors=nullptr;
        if (FAILED(D3DCompile(kDetailHlsl,sizeof(kDetailHlsl)-1,nullptr,nullptr,nullptr,"main","cs_5_0",
                             D3DCOMPILE_OPTIMIZATION_LEVEL3,0,code.put(),errors.put()))) return false;
        D3D12_COMPUTE_PIPELINE_STATE_DESC pd{};pd.pRootSignature=d.root.get();
        pd.CS={code->GetBufferPointer(),code->GetBufferSize()};
        if (FAILED(h.dev->CreateComputePipelineState(&pd,IID_PPV_ARGS(d.pipeline.put())))) return false;
    }
    if (d.output == v.output) return true;
    CloseDetailResources();
    const auto desc = v.output->GetDesc();
    d.input.attach(MakeTex(UINT(desc.Width),desc.Height,desc.Format,false));
    D3D12_DESCRIPTOR_HEAP_DESC hd={D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV,2,D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE,0};
    if (!d.input || FAILED(h.dev->CreateDescriptorHeap(&hd,IID_PPV_ARGS(d.heap.put())))) return false;
    auto cpu=d.heap->GetCPUDescriptorHandleForHeapStart();
    D3D12_SHADER_RESOURCE_VIEW_DESC sd{};sd.Format=desc.Format;sd.ViewDimension=D3D12_SRV_DIMENSION_TEXTURE2D;
    sd.Shader4ComponentMapping=D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;sd.Texture2D.MipLevels=1;
    h.dev->CreateShaderResourceView(d.input.get(),&sd,cpu);
    cpu.ptr+=h.dev->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
    D3D12_UNORDERED_ACCESS_VIEW_DESC ud{};ud.Format=desc.Format;ud.ViewDimension=D3D12_UAV_DIMENSION_TEXTURE2D;
    h.dev->CreateUnorderedAccessView(v.output,nullptr,&ud,cpu);
    d.output=v.output;
    return true;
}

// Run on NR output, independently of SR/DLAA, before HDR reconstruction, FG and pixel export.
// Strength zero does not allocate, copy, or dispatch. Bypass never calls here.
static void ApplyDetail(VideoState &v)
{
    if (!g_detail_strength) return;
    if (!EnsureDetail(v)) {
        Log("[detail] unavailable; keeping NR output");g_detail_strength=0;return;
    }
    auto &d=g_detail;
    D3D12_RESOURCE_BARRIER before[]={
        Transition(v.output,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE),
        Transition(d.input.get(),D3D12_RESOURCE_STATE_COMMON,D3D12_RESOURCE_STATE_COPY_DEST)};
    h.list->ResourceBarrier(2,before);
    h.list->CopyResource(d.input.get(),v.output);
    D3D12_RESOURCE_BARRIER copied[]={
        Transition(v.output,D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_UNORDERED_ACCESS),
        Transition(d.input.get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE)};
    h.list->ResourceBarrier(2,copied);
    auto heap=d.heap.get();h.list->SetDescriptorHeaps(1,&heap);
    h.list->SetComputeRootSignature(d.root.get());h.list->SetPipelineState(d.pipeline.get());
    const auto desc=v.output->GetDesc();
    struct { UINT width,height;float strength; } params={UINT(desc.Width),desc.Height,g_detail_strength/100.f};
    h.list->SetComputeRoot32BitConstants(0,3,&params,0);
    h.list->SetComputeRootDescriptorTable(1,d.heap->GetGPUDescriptorHandleForHeapStart());
    h.list->Dispatch((params.width+7)/8,(params.height+7)/8,1);
    auto after=Transition(d.input.get(),D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_COMMON);
    h.list->ResourceBarrier(1,&after);
}
