import { ref } from 'vue';
import { http } from '../api/http';
const q = ref('年假制度');
const result = ref(null);
const error = ref('');
async function search() { try {
    result.value = (await http.post('/knowledge/search', { query: q.value, top_k: 5 })).data;
}
catch (e) {
    error.value = e.response?.data?.detail || '检索失败';
} }
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
    modelValue: (__VLS_ctx.q),
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.q),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
elButton;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onClick': {} },
}));
const __VLS_7 = __VLS_6({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = {
    /** @type {typeof __VLS_10.click} */
    onClick: (__VLS_ctx.search),
};
const { default: __VLS_12 } = __VLS_8.slots;
// @ts-ignore
[q, search,];
var __VLS_8;
var __VLS_9;
if (__VLS_ctx.error) {
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.elAlert | typeof __VLS_components.ElAlert | typeof __VLS_components['el-alert']} */
    elAlert;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        type: "warning",
        title: (__VLS_ctx.error),
    }));
    const __VLS_15 = __VLS_14({
        type: "warning",
        title: (__VLS_ctx.error),
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
}
if (__VLS_ctx.result) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.pre, __VLS_intrinsics.pre)({});
    (JSON.stringify(__VLS_ctx.result, null, 2));
}
// @ts-ignore
[error, error, result, result,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
