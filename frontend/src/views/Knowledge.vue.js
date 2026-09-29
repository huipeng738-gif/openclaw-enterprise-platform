import { onMounted, ref } from 'vue';
import { http } from '../api/http';
import { role } from '../stores/auth';
const datasets = ref([]);
const documents = ref([]);
const datasetId = ref('');
const retrievalIds = ref([]);
const query = ref('年假制度');
const chunks = ref([]);
const datasetName = ref('');
const existingDatasetId = ref('');
const uploadFile = ref(null);
const error = ref('');
const busy = ref(false);
const loading = ref(false);
const topK = ref(5);
const threshold = ref(0.2);
let documentRequest = 0;
function detail(e, fallback) { return e.response?.data?.detail || fallback; }
async function loadDatasets() {
    loading.value = true;
    error.value = '';
    try {
        datasets.value = (await http.get('/knowledge/bases')).data;
        if (!datasets.value.some(item => item.id === datasetId.value))
            datasetId.value = datasets.value[0]?.id || '';
        retrievalIds.value = retrievalIds.value.filter(id => datasets.value.some(item => item.id === id));
        if (!retrievalIds.value.length && datasetId.value)
            retrievalIds.value = [datasetId.value];
        await loadDocuments();
    }
    catch (e) {
        error.value = detail(e, '加载知识库失败');
    }
    finally {
        loading.value = false;
    }
}
async function loadDocuments() {
    const request = ++documentRequest;
    const selected = datasetId.value;
    documents.value = [];
    if (!selected)
        return;
    try {
        const data = (await http.get(`/knowledge/bases/${selected}/documents`)).data;
        if (request === documentRequest)
            documents.value = data.docs || [];
    }
    catch (e) {
        if (request === documentRequest)
            error.value = detail(e, '加载文档失败');
    }
}
async function search() {
    if (!retrievalIds.value.length || !query.value.trim())
        return;
    error.value = '';
    busy.value = true;
    chunks.value = [];
    try {
        const data = (await http.post('/knowledge/retrieval', {
            query: query.value, top_k: topK.value, similarity_threshold: threshold.value,
            knowledge_base_ids: retrievalIds.value
        })).data;
        chunks.value = data.results || [];
    }
    catch (e) {
        error.value = detail(e, '检索失败');
    }
    finally {
        busy.value = false;
    }
}
async function createDataset() {
    if (!datasetName.value.trim())
        return;
    error.value = '';
    busy.value = true;
    try {
        const created = (await http.post('/knowledge/bases', { name: datasetName.value.trim() })).data;
        datasetName.value = '';
        await loadDatasets();
        datasetId.value = created.id;
        await loadDocuments();
    }
    catch (e) {
        error.value = detail(e, '创建知识库失败');
    }
    finally {
        busy.value = false;
    }
}
async function registerDataset() {
    if (!existingDatasetId.value.trim())
        return;
    error.value = '';
    busy.value = true;
    try {
        await http.post(`/knowledge/datasets/${existingDatasetId.value.trim()}/register`);
        datasetId.value = existingDatasetId.value.trim();
        existingDatasetId.value = '';
        await loadDatasets();
    }
    catch (e) {
        error.value = detail(e, '关联知识库失败');
    }
    finally {
        busy.value = false;
    }
}
function selectFile(event) {
    uploadFile.value = event.target.files?.[0] || null;
}
async function upload() {
    if (!datasetId.value || !uploadFile.value)
        return;
    error.value = '';
    busy.value = true;
    try {
        const form = new FormData();
        form.append('file', uploadFile.value);
        await http.post(`/knowledge/bases/${datasetId.value}/documents`, form);
        uploadFile.value = null;
        await loadDocuments();
    }
    catch (e) {
        error.value = detail(e, '上传文档失败');
    }
    finally {
        busy.value = false;
    }
}
async function parse(document) {
    error.value = '';
    busy.value = true;
    try {
        await http.post(`/knowledge/bases/${datasetId.value}/documents/${document.id}/parse`);
        await loadDocuments();
    }
    catch (e) {
        error.value = detail(e, '启动解析失败');
    }
    finally {
        busy.value = false;
    }
}
async function removeDataset() {
    const selected = datasetId.value;
    if (!selected || !confirm('确认删除此知识库及其文档？'))
        return;
    error.value = '';
    busy.value = true;
    try {
        await http.delete(`/knowledge/bases/${selected}`);
        datasetId.value = '';
        await loadDatasets();
    }
    catch (e) {
        error.value = detail(e, '删除知识库失败');
    }
    finally {
        busy.value = false;
    }
}
async function removeDocument(document) {
    if (!confirm(`确认删除 ${document.name}？`))
        return;
    error.value = '';
    busy.value = true;
    try {
        await http.delete(`/knowledge/bases/${datasetId.value}/documents/${document.id}`);
        await loadDocuments();
    }
    catch (e) {
        error.value = detail(e, '删除文档失败');
    }
    finally {
        busy.value = false;
    }
}
async function refreshStatus(document) {
    try {
        const status = (await http.get(`/knowledge/bases/${datasetId.value}/documents/${document.id}/status`)).data;
        Object.assign(document, status);
    }
    catch (e) {
        error.value = detail(e, '刷新解析状态失败');
    }
}
function displayStatus(run) {
    return { UNSTART: 'pending', RUNNING: 'parsing', DONE: 'completed', FAIL: 'failed', CANCEL: 'failed' }[run || ''] || run || 'pending';
}
onMounted(loadDatasets);
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "page-title" },
});
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
if (__VLS_ctx.error) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.elAlert | typeof __VLS_components.ElAlert | typeof __VLS_components['el-alert']} */
    elAlert;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        type: "error",
        title: (__VLS_ctx.error),
        showIcon: true,
    }));
    const __VLS_2 = __VLS_1({
        type: "error",
        title: (__VLS_ctx.error),
        showIcon: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
__VLS_asFunctionalDirective(__VLS_directives.vLoading, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.loading), }, null, null);
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar" },
});
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.elSelect | typeof __VLS_components.ElSelect | typeof __VLS_components['el-select'] | typeof __VLS_components.elSelect | typeof __VLS_components.ElSelect | typeof __VLS_components['el-select']} */
elSelect;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.datasetId),
    placeholder: "选择知识库",
    ...{ style: {} },
}));
const __VLS_7 = __VLS_6({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.datasetId),
    placeholder: "选择知识库",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = {
    /** @type {typeof __VLS_10.change} */
    onChange: (__VLS_ctx.loadDocuments),
};
const { default: __VLS_12 } = __VLS_8.slots;
for (const [item] of __VLS_vFor((__VLS_ctx.datasets))) {
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.elOption | typeof __VLS_components.ElOption | typeof __VLS_components['el-option']} */
    elOption;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        key: (item.id),
        label: (item.name),
        value: (item.id),
    }));
    const __VLS_15 = __VLS_14({
        key: (item.id),
        label: (item.name),
        value: (item.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
    // @ts-ignore
    [error, error, vLoading, loading, datasetId, loadDocuments, datasets,];
}
// @ts-ignore
[];
var __VLS_8;
var __VLS_9;
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
elButton;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
    ...{ 'onClick': {} },
}));
const __VLS_20 = __VLS_19({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
let __VLS_23;
const __VLS_24 = {
    /** @type {typeof __VLS_23.click} */
    onClick: (__VLS_ctx.loadDatasets),
};
const { default: __VLS_25 } = __VLS_21.slots;
// @ts-ignore
[loadDatasets,];
var __VLS_21;
var __VLS_22;
let __VLS_26;
/** @ts-ignore @type { | typeof __VLS_components.elSelect | typeof __VLS_components.ElSelect | typeof __VLS_components['el-select'] | typeof __VLS_components.elSelect | typeof __VLS_components.ElSelect | typeof __VLS_components['el-select']} */
elSelect;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
    modelValue: (__VLS_ctx.retrievalIds),
    multiple: true,
    placeholder: "检索知识库",
    ...{ style: {} },
}));
const __VLS_28 = __VLS_27({
    modelValue: (__VLS_ctx.retrievalIds),
    multiple: true,
    placeholder: "检索知识库",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
const { default: __VLS_31 } = __VLS_29.slots;
for (const [item] of __VLS_vFor((__VLS_ctx.datasets))) {
    let __VLS_32;
    /** @ts-ignore @type { | typeof __VLS_components.elOption | typeof __VLS_components.ElOption | typeof __VLS_components['el-option']} */
    elOption;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
        key: (item.id),
        label: (item.name),
        value: (item.id),
    }));
    const __VLS_34 = __VLS_33({
        key: (item.id),
        label: (item.name),
        value: (item.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    // @ts-ignore
    [datasets, retrievalIds,];
}
// @ts-ignore
[];
var __VLS_29;
let __VLS_37;
/** @ts-ignore @type { | typeof __VLS_components.elInputNumber | typeof __VLS_components.ElInputNumber | typeof __VLS_components['el-input-number']} */
elInputNumber;
// @ts-ignore
const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
    modelValue: (__VLS_ctx.topK),
    min: (1),
    max: (20),
    'aria-label': "返回条数",
}));
const __VLS_39 = __VLS_38({
    modelValue: (__VLS_ctx.topK),
    min: (1),
    max: (20),
    'aria-label': "返回条数",
}, ...__VLS_functionalComponentArgsRest(__VLS_38));
let __VLS_42;
/** @ts-ignore @type { | typeof __VLS_components.elInputNumber | typeof __VLS_components.ElInputNumber | typeof __VLS_components['el-input-number']} */
elInputNumber;
// @ts-ignore
const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
    modelValue: (__VLS_ctx.threshold),
    min: (0),
    max: (1),
    step: (0.05),
    'aria-label': "相似度阈值",
}));
const __VLS_44 = __VLS_43({
    modelValue: (__VLS_ctx.threshold),
    min: (0),
    max: (1),
    step: (0.05),
    'aria-label': "相似度阈值",
}, ...__VLS_functionalComponentArgsRest(__VLS_43));
let __VLS_47;
/** @ts-ignore @type { | typeof __VLS_components.elInput | typeof __VLS_components.ElInput | typeof __VLS_components['el-input']} */
elInput;
// @ts-ignore
const __VLS_48 = __VLS_asFunctionalComponent1(__VLS_47, new __VLS_47({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.query),
    placeholder: "输入检索问题",
}));
const __VLS_49 = __VLS_48({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.query),
    placeholder: "输入检索问题",
}, ...__VLS_functionalComponentArgsRest(__VLS_48));
let __VLS_52;
const __VLS_53 = {
    /** @type {typeof __VLS_52.keyup} */
    onKeyup: (__VLS_ctx.search),
};
var __VLS_50;
var __VLS_51;
let __VLS_54;
/** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
elButton;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.busy),
    disabled: (!__VLS_ctx.retrievalIds.length),
}));
const __VLS_56 = __VLS_55({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.busy),
    disabled: (!__VLS_ctx.retrievalIds.length),
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
let __VLS_59;
const __VLS_60 = {
    /** @type {typeof __VLS_59.click} */
    onClick: (__VLS_ctx.search),
};
const { default: __VLS_61 } = __VLS_57.slots;
// @ts-ignore
[retrievalIds, topK, threshold, query, search, search, busy,];
var __VLS_57;
var __VLS_58;
if (!__VLS_ctx.loading && !__VLS_ctx.datasets.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
}
if (__VLS_ctx.datasets.length) {
    let __VLS_62;
    /** @ts-ignore @type { | typeof __VLS_components.elTable | typeof __VLS_components.ElTable | typeof __VLS_components['el-table'] | typeof __VLS_components.elTable | typeof __VLS_components.ElTable | typeof __VLS_components['el-table']} */
    elTable;
    // @ts-ignore
    const __VLS_63 = __VLS_asFunctionalComponent1(__VLS_62, new __VLS_62({
        ...{ 'onRowClick': {} },
        data: (__VLS_ctx.datasets),
    }));
    const __VLS_64 = __VLS_63({
        ...{ 'onRowClick': {} },
        data: (__VLS_ctx.datasets),
    }, ...__VLS_functionalComponentArgsRest(__VLS_63));
    let __VLS_67;
    const __VLS_68 = {
        /** @type {typeof __VLS_67.rowClick} */
        onRowClick: ((row) => { __VLS_ctx.datasetId = row.id; __VLS_ctx.loadDocuments(); }),
    };
    const { default: __VLS_69 } = __VLS_65.slots;
    let __VLS_70;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_71 = __VLS_asFunctionalComponent1(__VLS_70, new __VLS_70({
        prop: "name",
        label: "名称",
    }));
    const __VLS_72 = __VLS_71({
        prop: "name",
        label: "名称",
    }, ...__VLS_functionalComponentArgsRest(__VLS_71));
    let __VLS_75;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_76 = __VLS_asFunctionalComponent1(__VLS_75, new __VLS_75({
        prop: "description",
        label: "描述",
    }));
    const __VLS_77 = __VLS_76({
        prop: "description",
        label: "描述",
    }, ...__VLS_functionalComponentArgsRest(__VLS_76));
    let __VLS_80;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent1(__VLS_80, new __VLS_80({
        prop: "document_count",
        label: "文档数",
        width: "100",
    }));
    const __VLS_82 = __VLS_81({
        prop: "document_count",
        label: "文档数",
        width: "100",
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    let __VLS_85;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_86 = __VLS_asFunctionalComponent1(__VLS_85, new __VLS_85({
        prop: "status",
        label: "状态",
        width: "100",
    }));
    const __VLS_87 = __VLS_86({
        prop: "status",
        label: "状态",
        width: "100",
    }, ...__VLS_functionalComponentArgsRest(__VLS_86));
    let __VLS_90;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_91 = __VLS_asFunctionalComponent1(__VLS_90, new __VLS_90({
        prop: "update_date",
        label: "更新时间",
        width: "200",
    }));
    const __VLS_92 = __VLS_91({
        prop: "update_date",
        label: "更新时间",
        width: "200",
    }, ...__VLS_functionalComponentArgsRest(__VLS_91));
    // @ts-ignore
    [loading, datasetId, loadDocuments, datasets, datasets, datasets,];
    var __VLS_65;
    var __VLS_66;
}
for (const [chunk] of __VLS_vFor((__VLS_ctx.chunks))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (chunk.id),
        ...{ class: "event" },
    });
    /** @type {__VLS_StyleScopedClasses['event']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    (chunk.document_name || '未知来源');
    (chunk.score?.toFixed(2));
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
    (chunk.content);
    if (chunk.metadata && Object.keys(chunk.metadata).length) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.small, __VLS_intrinsics.small)({});
        (chunk.metadata);
    }
    // @ts-ignore
    [chunks,];
}
if (__VLS_ctx.datasetId && !__VLS_ctx.busy && !__VLS_ctx.chunks.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
}
if (__VLS_ctx.datasetId) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "card" },
    });
    /** @type {__VLS_StyleScopedClasses['card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({});
    (__VLS_ctx.datasets.find(item => item.id === __VLS_ctx.datasetId)?.name);
    if (__VLS_ctx.role === 'admin') {
        let __VLS_95;
        /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
        elButton;
        // @ts-ignore
        const __VLS_96 = __VLS_asFunctionalComponent1(__VLS_95, new __VLS_95({
            ...{ 'onClick': {} },
            type: "danger",
            disabled: (__VLS_ctx.busy),
        }));
        const __VLS_97 = __VLS_96({
            ...{ 'onClick': {} },
            type: "danger",
            disabled: (__VLS_ctx.busy),
        }, ...__VLS_functionalComponentArgsRest(__VLS_96));
        let __VLS_100;
        const __VLS_101 = {
            /** @type {typeof __VLS_100.click} */
            onClick: (__VLS_ctx.removeDataset),
        };
        const { default: __VLS_102 } = __VLS_98.slots;
        // @ts-ignore
        [datasetId, datasetId, datasetId, datasets, busy, busy, chunks, role, removeDataset,];
        var __VLS_98;
        var __VLS_99;
    }
    let __VLS_103;
    /** @ts-ignore @type { | typeof __VLS_components.elTable | typeof __VLS_components.ElTable | typeof __VLS_components['el-table'] | typeof __VLS_components.elTable | typeof __VLS_components.ElTable | typeof __VLS_components['el-table']} */
    elTable;
    // @ts-ignore
    const __VLS_104 = __VLS_asFunctionalComponent1(__VLS_103, new __VLS_103({
        data: (__VLS_ctx.documents),
    }));
    const __VLS_105 = __VLS_104({
        data: (__VLS_ctx.documents),
    }, ...__VLS_functionalComponentArgsRest(__VLS_104));
    const { default: __VLS_108 } = __VLS_106.slots;
    let __VLS_109;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_110 = __VLS_asFunctionalComponent1(__VLS_109, new __VLS_109({
        prop: "name",
        label: "名称",
    }));
    const __VLS_111 = __VLS_110({
        prop: "name",
        label: "名称",
    }, ...__VLS_functionalComponentArgsRest(__VLS_110));
    let __VLS_114;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column'] | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_115 = __VLS_asFunctionalComponent1(__VLS_114, new __VLS_114({
        label: "解析状态",
        width: "150",
    }));
    const __VLS_116 = __VLS_115({
        label: "解析状态",
        width: "150",
    }, ...__VLS_functionalComponentArgsRest(__VLS_115));
    const { default: __VLS_119 } = __VLS_117.slots;
    {
        const { default: __VLS_120 } = __VLS_117.slots;
        const [scope] = __VLS_vSlot(__VLS_120);
        (__VLS_ctx.displayStatus(scope.row.run));
        // @ts-ignore
        [documents, displayStatus,];
    }
    // @ts-ignore
    [];
    var __VLS_117;
    let __VLS_121;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_122 = __VLS_asFunctionalComponent1(__VLS_121, new __VLS_121({
        prop: "chunk_count",
        label: "Chunk 数",
        width: "110",
    }));
    const __VLS_123 = __VLS_122({
        prop: "chunk_count",
        label: "Chunk 数",
        width: "110",
    }, ...__VLS_functionalComponentArgsRest(__VLS_122));
    let __VLS_126;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_127 = __VLS_asFunctionalComponent1(__VLS_126, new __VLS_126({
        prop: "update_date",
        label: "更新时间",
        width: "200",
    }));
    const __VLS_128 = __VLS_127({
        prop: "update_date",
        label: "更新时间",
        width: "200",
    }, ...__VLS_functionalComponentArgsRest(__VLS_127));
    let __VLS_131;
    /** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column'] | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
    elTableColumn;
    // @ts-ignore
    const __VLS_132 = __VLS_asFunctionalComponent1(__VLS_131, new __VLS_131({
        label: "操作",
        width: "240",
    }));
    const __VLS_133 = __VLS_132({
        label: "操作",
        width: "240",
    }, ...__VLS_functionalComponentArgsRest(__VLS_132));
    const { default: __VLS_136 } = __VLS_134.slots;
    {
        const { default: __VLS_137 } = __VLS_134.slots;
        const [scope] = __VLS_vSlot(__VLS_137);
        let __VLS_138;
        /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
        elButton;
        // @ts-ignore
        const __VLS_139 = __VLS_asFunctionalComponent1(__VLS_138, new __VLS_138({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_140 = __VLS_139({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_139));
        let __VLS_143;
        const __VLS_144 = {
            /** @type {typeof __VLS_143.click} */
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.datasetId))
                    throw 0;
                return (__VLS_ctx.refreshStatus(scope.row));
                // @ts-ignore
                [refreshStatus,];
            },
        };
        const { default: __VLS_145 } = __VLS_141.slots;
        // @ts-ignore
        [];
        var __VLS_141;
        var __VLS_142;
        if (__VLS_ctx.role === 'admin') {
            let __VLS_146;
            /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
            elButton;
            // @ts-ignore
            const __VLS_147 = __VLS_asFunctionalComponent1(__VLS_146, new __VLS_146({
                ...{ 'onClick': {} },
                size: "small",
                disabled: (__VLS_ctx.busy),
            }));
            const __VLS_148 = __VLS_147({
                ...{ 'onClick': {} },
                size: "small",
                disabled: (__VLS_ctx.busy),
            }, ...__VLS_functionalComponentArgsRest(__VLS_147));
            let __VLS_151;
            const __VLS_152 = {
                /** @type {typeof __VLS_151.click} */
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.datasetId))
                        throw 0;
                    if (!(__VLS_ctx.role === 'admin'))
                        throw 0;
                    return (__VLS_ctx.parse(scope.row));
                    // @ts-ignore
                    [busy, role, parse,];
                },
            };
            const { default: __VLS_153 } = __VLS_149.slots;
            // @ts-ignore
            [];
            var __VLS_149;
            var __VLS_150;
        }
        if (__VLS_ctx.role === 'admin') {
            let __VLS_154;
            /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
            elButton;
            // @ts-ignore
            const __VLS_155 = __VLS_asFunctionalComponent1(__VLS_154, new __VLS_154({
                ...{ 'onClick': {} },
                size: "small",
                type: "danger",
                disabled: (__VLS_ctx.busy),
            }));
            const __VLS_156 = __VLS_155({
                ...{ 'onClick': {} },
                size: "small",
                type: "danger",
                disabled: (__VLS_ctx.busy),
            }, ...__VLS_functionalComponentArgsRest(__VLS_155));
            let __VLS_159;
            const __VLS_160 = {
                /** @type {typeof __VLS_159.click} */
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.datasetId))
                        throw 0;
                    if (!(__VLS_ctx.role === 'admin'))
                        throw 0;
                    return (__VLS_ctx.removeDocument(scope.row));
                    // @ts-ignore
                    [busy, role, removeDocument,];
                },
            };
            const { default: __VLS_161 } = __VLS_157.slots;
            // @ts-ignore
            [];
            var __VLS_157;
            var __VLS_158;
        }
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_134;
    // @ts-ignore
    [];
    var __VLS_106;
    if (__VLS_ctx.role === 'admin') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "toolbar" },
        });
        /** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
            ...{ onChange: (__VLS_ctx.selectFile) },
            type: "file",
        });
        let __VLS_162;
        /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
        elButton;
        // @ts-ignore
        const __VLS_163 = __VLS_asFunctionalComponent1(__VLS_162, new __VLS_162({
            ...{ 'onClick': {} },
            disabled: (!__VLS_ctx.uploadFile || __VLS_ctx.busy),
        }));
        const __VLS_164 = __VLS_163({
            ...{ 'onClick': {} },
            disabled: (!__VLS_ctx.uploadFile || __VLS_ctx.busy),
        }, ...__VLS_functionalComponentArgsRest(__VLS_163));
        let __VLS_167;
        const __VLS_168 = {
            /** @type {typeof __VLS_167.click} */
            onClick: (__VLS_ctx.upload),
        };
        const { default: __VLS_169 } = __VLS_165.slots;
        // @ts-ignore
        [busy, role, selectFile, uploadFile, upload,];
        var __VLS_165;
        var __VLS_166;
    }
}
if (__VLS_ctx.role === 'admin') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "card" },
    });
    /** @type {__VLS_StyleScopedClasses['card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "toolbar" },
    });
    /** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
    let __VLS_170;
    /** @ts-ignore @type { | typeof __VLS_components.elInput | typeof __VLS_components.ElInput | typeof __VLS_components['el-input']} */
    elInput;
    // @ts-ignore
    const __VLS_171 = __VLS_asFunctionalComponent1(__VLS_170, new __VLS_170({
        modelValue: (__VLS_ctx.datasetName),
        placeholder: "新知识库名称",
    }));
    const __VLS_172 = __VLS_171({
        modelValue: (__VLS_ctx.datasetName),
        placeholder: "新知识库名称",
    }, ...__VLS_functionalComponentArgsRest(__VLS_171));
    let __VLS_175;
    /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
    elButton;
    // @ts-ignore
    const __VLS_176 = __VLS_asFunctionalComponent1(__VLS_175, new __VLS_175({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.busy),
    }));
    const __VLS_177 = __VLS_176({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.busy),
    }, ...__VLS_functionalComponentArgsRest(__VLS_176));
    let __VLS_180;
    const __VLS_181 = {
        /** @type {typeof __VLS_180.click} */
        onClick: (__VLS_ctx.createDataset),
    };
    const { default: __VLS_182 } = __VLS_178.slots;
    // @ts-ignore
    [busy, role, datasetName, createDataset,];
    var __VLS_178;
    var __VLS_179;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "toolbar" },
    });
    /** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
    let __VLS_183;
    /** @ts-ignore @type { | typeof __VLS_components.elInput | typeof __VLS_components.ElInput | typeof __VLS_components['el-input']} */
    elInput;
    // @ts-ignore
    const __VLS_184 = __VLS_asFunctionalComponent1(__VLS_183, new __VLS_183({
        modelValue: (__VLS_ctx.existingDatasetId),
        placeholder: "已有 RAGFlow 数据集 ID",
    }));
    const __VLS_185 = __VLS_184({
        modelValue: (__VLS_ctx.existingDatasetId),
        placeholder: "已有 RAGFlow 数据集 ID",
    }, ...__VLS_functionalComponentArgsRest(__VLS_184));
    let __VLS_188;
    /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
    elButton;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent1(__VLS_188, new __VLS_188({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.busy),
    }));
    const __VLS_190 = __VLS_189({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.busy),
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    let __VLS_193;
    const __VLS_194 = {
        /** @type {typeof __VLS_193.click} */
        onClick: (__VLS_ctx.registerDataset),
    };
    const { default: __VLS_195 } = __VLS_191.slots;
    // @ts-ignore
    [busy, existingDatasetId, registerDataset,];
    var __VLS_191;
    var __VLS_192;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
