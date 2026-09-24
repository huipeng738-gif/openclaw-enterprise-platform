import { ref, onUnmounted } from 'vue';
import { http } from '../api/http';
const input = ref('');
const messages = ref([]);
const tools = ref([]);
const loading = ref(false);
const error = ref('');
let ws;
async function send() {
    if (!input.value.trim() || loading.value)
        return;
    const q = input.value;
    input.value = '';
    messages.value.push({ role: 'user', text: q });
    tools.value = [];
    loading.value = true;
    error.value = '';
    try {
        const task = (await http.post('/chat', { prompt: q })).data;
        const ticket = (await http.post(`/tasks/${task.id}/ws-ticket`)).data.ticket;
        const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(`${protocol}://${location.host}/ws/tasks/${task.id}?ticket=${encodeURIComponent(ticket)}`);
        ws.onmessage = e => { const msg = JSON.parse(e.data); if (msg.type === 'event' && msg.event.kind === 'tool')
            tools.value.push(msg.event); if (msg.type === 'snapshot' && ['completed', 'failed', 'cancelled', 'timed_out'].includes(msg.task.status)) {
            messages.value.push({ role: 'assistant', text: msg.task.result || msg.task.error || msg.task.status });
            loading.value = false;
            ws?.close();
        } };
        ws.onerror = () => { error.value = '实时连接中断，请在任务中心查看结果'; loading.value = false; };
    }
    catch (e) {
        error.value = e.response?.data?.detail || '请求失败';
        loading.value = false;
    }
}
onUnmounted(() => ws?.close());
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
    ...{ class: "chat-box" },
});
/** @type {__VLS_StyleScopedClasses['chat-box']} */ ;
for (const [m, i] of __VLS_vFor((__VLS_ctx.messages))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (i),
        ...{ class: "msg" },
        ...{ class: (m.role) },
    });
    /** @type {__VLS_StyleScopedClasses['msg']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "bubble" },
    });
    /** @type {__VLS_StyleScopedClasses['bubble']} */ ;
    (m.text);
    // @ts-ignore
    [messages,];
}
if (__VLS_ctx.tools.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "card" },
    });
    /** @type {__VLS_StyleScopedClasses['card']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.b, __VLS_intrinsics.b)({});
    for (const [t, i] of __VLS_vFor((__VLS_ctx.tools))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (i),
        });
        (t.name);
        (t.phase);
        // @ts-ignore
        [tools, tools,];
    }
}
if (__VLS_ctx.error) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.elAlert | typeof __VLS_components.ElAlert | typeof __VLS_components['el-alert']} */
    elAlert;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        type: "error",
        title: (__VLS_ctx.error),
    }));
    const __VLS_2 = __VLS_1({
        type: "error",
        title: (__VLS_ctx.error),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar" },
});
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.elInput | typeof __VLS_components.ElInput | typeof __VLS_components['el-input']} */
elInput;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.input),
}));
const __VLS_7 = __VLS_6({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.input),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = {
    /** @type {typeof __VLS_10.keyup} */
    onKeyup: (__VLS_ctx.send),
};
var __VLS_8;
var __VLS_9;
let __VLS_12;
/** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
elButton;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_17;
const __VLS_18 = {
    /** @type {typeof __VLS_17.click} */
    onClick: (__VLS_ctx.send),
};
const { default: __VLS_19 } = __VLS_15.slots;
// @ts-ignore
[error, error, input, send, send, loading,];
var __VLS_15;
var __VLS_16;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
