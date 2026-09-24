import { onMounted, ref } from 'vue';
import { http } from '../api/http';
const data = ref({});
const error = ref('');
onMounted(async () => { try {
    data.value = (await http.get('/dashboard')).data;
}
catch {
    error.value = '加载失败';
} });
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
    }));
    const __VLS_2 = __VLS_1({
        type: "error",
        title: (__VLS_ctx.error),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "grid" },
});
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "metric" },
});
/** @type {__VLS_StyleScopedClasses['metric']} */ ;
(__VLS_ctx.data.agentCount ?? '-');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "metric" },
});
/** @type {__VLS_StyleScopedClasses['metric']} */ ;
(__VLS_ctx.data.runningTasks ?? '-');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "metric" },
});
/** @type {__VLS_StyleScopedClasses['metric']} */ ;
(__VLS_ctx.data.completedTasks ?? '-');
// @ts-ignore
[error, error, data, data, data,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
