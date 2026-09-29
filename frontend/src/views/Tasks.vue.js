import { ref, onMounted, onUnmounted } from 'vue';
import { http } from '../api/http';
const prompt = ref('总结本周企业经营数据');
const tasks = ref([]);
const selected = ref(null);
const events = ref([]);
const error = ref('');
let ws;
let watchVersion = 0;
const terminal = ['completed', 'failed', 'cancelled', 'timed_out'];
async function load() {
    try {
        tasks.value = (await http.get('/tasks')).data;
    }
    catch (e) {
        error.value = e.response?.data?.detail || '加载任务列表失败';
    }
}
async function watch(task) {
    const version = ++watchVersion;
    ws?.close();
    ws = undefined;
    error.value = '';
    selected.value = task;
    events.value = [];
    try {
        const history = (await http.get(`/tasks/${task.id}/events`)).data;
        if (version !== watchVersion)
            return;
        events.value = history;
        if (terminal.includes(task.status))
            return;
        const ticket = (await http.post(`/tasks/${task.id}/ws-ticket`)).data.ticket;
        if (version !== watchVersion)
            return;
        const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
        const socket = new WebSocket(`${protocol}://${location.host}/ws/tasks/${task.id}?ticket=${encodeURIComponent(ticket)}`);
        ws = socket;
        socket.onmessage = e => {
            if (version !== watchVersion)
                return;
            const msg = JSON.parse(e.data);
            if (msg.type === 'snapshot') {
                selected.value = msg.task;
                const i = tasks.value.findIndex(t => t.id === msg.task.id);
                if (i >= 0)
                    tasks.value[i] = msg.task;
            }
            else if (msg.type === 'event' && !events.value.some(x => x.id === msg.id)) {
                events.value.push({ id: msg.id, ...msg.event });
            }
        };
        socket.onclose = () => {
            if (version === watchVersion && !terminal.includes(selected.value?.status))
                error.value = '实时连接中断，请重新点选任务';
            if (ws === socket)
                ws = undefined;
        };
    }
    catch (e) {
        if (version === watchVersion)
            error.value = e.response?.data?.detail || '读取任务事件或建立实时连接失败';
    }
}
async function create() {
    error.value = '';
    let task;
    try {
        task = (await http.post('/tasks', { prompt: prompt.value })).data;
    }
    catch (e) {
        error.value = e.response?.data?.detail || '创建失败';
        return;
    }
    tasks.value.unshift(task);
    await watch(task);
}
async function cancel(task) {
    try {
        await http.post(`/tasks/${task.id}/cancel`);
        await load();
    }
    catch (e) {
        error.value = e.response?.data?.detail || '取消任务失败';
    }
}
async function retry(task) {
    try {
        const newer = (await http.post(`/tasks/${task.id}/retry`)).data;
        tasks.value.unshift(newer);
        await watch(newer);
    }
    catch (e) {
        error.value = e.response?.data?.detail || '重试任务失败';
    }
}
onMounted(load);
onUnmounted(() => { watchVersion++; ws?.close(); });
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar" },
});
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.elInput | typeof __VLS_components.ElInput | typeof __VLS_components['el-input']} */
elInput;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.prompt),
    placeholder: "输入真实 Agent 任务",
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.prompt),
    placeholder: "输入真实 Agent 任务",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
elButton;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_7 = __VLS_6({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = {
    /** @type {typeof __VLS_10.click} */
    onClick: (__VLS_ctx.create),
};
const { default: __VLS_12 } = __VLS_8.slots;
// @ts-ignore
[prompt, create,];
var __VLS_8;
var __VLS_9;
if (__VLS_ctx.error) {
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.elAlert | typeof __VLS_components.ElAlert | typeof __VLS_components['el-alert']} */
    elAlert;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        type: "error",
        title: (__VLS_ctx.error),
    }));
    const __VLS_15 = __VLS_14({
        type: "error",
        title: (__VLS_ctx.error),
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
}
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.elTable | typeof __VLS_components.ElTable | typeof __VLS_components['el-table'] | typeof __VLS_components.elTable | typeof __VLS_components.ElTable | typeof __VLS_components['el-table']} */
elTable;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
    data: (__VLS_ctx.tasks),
}));
const __VLS_20 = __VLS_19({
    data: (__VLS_ctx.tasks),
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
const { default: __VLS_23 } = __VLS_21.slots;
let __VLS_24;
/** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
elTableColumn;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    prop: "prompt",
    label: "任务",
}));
const __VLS_26 = __VLS_25({
    prop: "prompt",
    label: "任务",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_29;
/** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
elTableColumn;
// @ts-ignore
const __VLS_30 = __VLS_asFunctionalComponent1(__VLS_29, new __VLS_29({
    prop: "status",
    label: "状态",
    width: "130",
}));
const __VLS_31 = __VLS_30({
    prop: "status",
    label: "状态",
    width: "130",
}, ...__VLS_functionalComponentArgsRest(__VLS_30));
let __VLS_34;
/** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
elTableColumn;
// @ts-ignore
const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({
    prop: "agent",
    label: "Agent",
    width: "140",
}));
const __VLS_36 = __VLS_35({
    prop: "agent",
    label: "Agent",
    width: "140",
}, ...__VLS_functionalComponentArgsRest(__VLS_35));
let __VLS_39;
/** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column'] | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
elTableColumn;
// @ts-ignore
const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
    label: "操作",
    width: "230",
}));
const __VLS_41 = __VLS_40({
    label: "操作",
    width: "230",
}, ...__VLS_functionalComponentArgsRest(__VLS_40));
const { default: __VLS_44 } = __VLS_42.slots;
{
    const { default: __VLS_45 } = __VLS_42.slots;
    const [s] = __VLS_vSlot(__VLS_45);
    let __VLS_46;
    /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
    elButton;
    // @ts-ignore
    const __VLS_47 = __VLS_asFunctionalComponent1(__VLS_46, new __VLS_46({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_48 = __VLS_47({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_47));
    let __VLS_51;
    const __VLS_52 = {
        /** @type {typeof __VLS_51.click} */
        onClick: (...[$event]) => {
            return (__VLS_ctx.watch(s.row));
            // @ts-ignore
            [error, error, tasks, watch,];
        },
    };
    const { default: __VLS_53 } = __VLS_49.slots;
    // @ts-ignore
    [];
    var __VLS_49;
    var __VLS_50;
    if (['queued', 'running'].includes(s.row.status)) {
        let __VLS_54;
        /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
        elButton;
        // @ts-ignore
        const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_56 = __VLS_55({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_55));
        let __VLS_59;
        const __VLS_60 = {
            /** @type {typeof __VLS_59.click} */
            onClick: (...[$event]) => {
                if (!(['queued', 'running'].includes(s.row.status)))
                    throw 0;
                return (__VLS_ctx.cancel(s.row));
                // @ts-ignore
                [cancel,];
            },
        };
        const { default: __VLS_61 } = __VLS_57.slots;
        // @ts-ignore
        [];
        var __VLS_57;
        var __VLS_58;
    }
    if (['failed', 'cancelled', 'timed_out'].includes(s.row.status)) {
        let __VLS_62;
        /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
        elButton;
        // @ts-ignore
        const __VLS_63 = __VLS_asFunctionalComponent1(__VLS_62, new __VLS_62({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_64 = __VLS_63({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_63));
        let __VLS_67;
        const __VLS_68 = {
            /** @type {typeof __VLS_67.click} */
            onClick: (...[$event]) => {
                if (!(['failed', 'cancelled', 'timed_out'].includes(s.row.status)))
                    throw 0;
                return (__VLS_ctx.retry(s.row));
                // @ts-ignore
                [retry,];
            },
        };
        const { default: __VLS_69 } = __VLS_65.slots;
        // @ts-ignore
        [];
        var __VLS_65;
        var __VLS_66;
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_42;
// @ts-ignore
[];
var __VLS_21;
if (__VLS_ctx.selected) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "card" },
    });
    /** @type {__VLS_StyleScopedClasses['card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({});
    (__VLS_ctx.selected.id);
    (__VLS_ctx.selected.status);
    if (__VLS_ctx.selected.error) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
        (__VLS_ctx.selected.error);
    }
    if (__VLS_ctx.selected.result) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.pre, __VLS_intrinsics.pre)({});
        (__VLS_ctx.selected.result);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({});
    for (const [event] of __VLS_vFor((__VLS_ctx.events))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (event.id),
            ...{ class: "event" },
        });
        /** @type {__VLS_StyleScopedClasses['event']} */ ;
        (event.kind);
        (event.name || event.phase || event.status || '');
        if (event.kind === 'assistant') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (event.text);
        }
        // @ts-ignore
        [selected, selected, selected, selected, selected, selected, selected, events,];
    }
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
