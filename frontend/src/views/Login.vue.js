import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { http } from '../api/http';
import { token, role } from '../stores/auth';
const router = useRouter();
const username = ref('');
const password = ref('');
const error = ref('');
async function login() {
    error.value = '';
    try {
        const { data } = await http.post('/auth/login', { username: username.value, password: password.value });
        token.value = data.access_token;
        role.value = data.role;
        router.push('/');
    }
    catch {
        error.value = '用户名或密码错误';
    }
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "login" },
});
/** @type {__VLS_StyleScopedClasses['login']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({});
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.elInput | typeof __VLS_components.ElInput | typeof __VLS_components['el-input']} */
elInput;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.username),
    placeholder: "用户名",
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.username),
    placeholder: "用户名",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.elInput | typeof __VLS_components.ElInput | typeof __VLS_components['el-input']} */
elInput;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.password),
    type: "password",
    placeholder: "密码",
    showPassword: true,
}));
const __VLS_7 = __VLS_6({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.password),
    type: "password",
    placeholder: "密码",
    showPassword: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = {
    /** @type {typeof __VLS_10.keyup} */
    onKeyup: (__VLS_ctx.login),
};
var __VLS_8;
var __VLS_9;
if (__VLS_ctx.error) {
    let __VLS_12;
    /** @ts-ignore @type { | typeof __VLS_components.elAlert | typeof __VLS_components.ElAlert | typeof __VLS_components['el-alert']} */
    elAlert;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
        type: "error",
        title: (__VLS_ctx.error),
    }));
    const __VLS_14 = __VLS_13({
        type: "error",
        title: (__VLS_ctx.error),
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
}
let __VLS_17;
/** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
elButton;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent1(__VLS_17, new __VLS_17({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_19 = __VLS_18({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
let __VLS_22;
const __VLS_23 = {
    /** @type {typeof __VLS_22.click} */
    onClick: (__VLS_ctx.login),
};
const { default: __VLS_24 } = __VLS_20.slots;
// @ts-ignore
[username, password, login, login, error, error,];
var __VLS_20;
var __VLS_21;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
