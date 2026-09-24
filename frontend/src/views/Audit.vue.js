import { onMounted, ref } from 'vue';
import { http } from '../api/http';
const rows = ref([]);
onMounted(async () => rows.value = (await http.get('/audit')).data);
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
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.elTable | typeof __VLS_components.ElTable | typeof __VLS_components['el-table'] | typeof __VLS_components.elTable | typeof __VLS_components.ElTable | typeof __VLS_components['el-table']} */
elTable;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    data: (__VLS_ctx.rows),
}));
const __VLS_2 = __VLS_1({
    data: (__VLS_ctx.rows),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
let __VLS_6;
/** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
elTableColumn;
// @ts-ignore
const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
    prop: "at",
    label: "时间",
}));
const __VLS_8 = __VLS_7({
    prop: "at",
    label: "时间",
}, ...__VLS_functionalComponentArgsRest(__VLS_7));
let __VLS_11;
/** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
elTableColumn;
// @ts-ignore
const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({
    prop: "actor",
    label: "操作人",
}));
const __VLS_13 = __VLS_12({
    prop: "actor",
    label: "操作人",
}, ...__VLS_functionalComponentArgsRest(__VLS_12));
let __VLS_16;
/** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
elTableColumn;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
    prop: "action",
    label: "动作",
}));
const __VLS_18 = __VLS_17({
    prop: "action",
    label: "动作",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_21;
/** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
elTableColumn;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
    prop: "target",
    label: "对象",
}));
const __VLS_23 = __VLS_22({
    prop: "target",
    label: "对象",
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
let __VLS_26;
/** @ts-ignore @type { | typeof __VLS_components.elTableColumn | typeof __VLS_components.ElTableColumn | typeof __VLS_components['el-table-column']} */
elTableColumn;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
    prop: "outcome",
    label: "结果",
}));
const __VLS_28 = __VLS_27({
    prop: "outcome",
    label: "结果",
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
// @ts-ignore
[rows,];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
