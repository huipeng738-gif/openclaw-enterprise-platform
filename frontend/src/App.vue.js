import { useRouter } from 'vue-router';
import { token, role, logout } from './stores/auth';
const router = useRouter();
function exit() { logout(); router.push('/login'); }
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
if (!__VLS_ctx.token) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.routerView | typeof __VLS_components.RouterView | typeof __VLS_components['router-view']} */
    routerView;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
    const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
    var __VLS_5;
    var __VLS_3;
}
else {
    let __VLS_6;
    /** @ts-ignore @type { | typeof __VLS_components.elContainer | typeof __VLS_components.ElContainer | typeof __VLS_components['el-container'] | typeof __VLS_components.elContainer | typeof __VLS_components.ElContainer | typeof __VLS_components['el-container']} */
    elContainer;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
        ...{ class: "shell" },
    }));
    const __VLS_8 = __VLS_7({
        ...{ class: "shell" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_7));
    var __VLS_11;
    /** @type {__VLS_StyleScopedClasses['shell']} */ ;
    const { default: __VLS_12 } = __VLS_9.slots;
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.elAside | typeof __VLS_components.ElAside | typeof __VLS_components['el-aside'] | typeof __VLS_components.elAside | typeof __VLS_components.ElAside | typeof __VLS_components['el-aside']} */
    elAside;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        width: "230px",
        ...{ class: "aside" },
    }));
    const __VLS_15 = __VLS_14({
        width: "230px",
        ...{ class: "aside" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
    /** @type {__VLS_StyleScopedClasses['aside']} */ ;
    const { default: __VLS_18 } = __VLS_16.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "brand" },
    });
    /** @type {__VLS_StyleScopedClasses['brand']} */ ;
    let __VLS_19;
    /** @ts-ignore @type { | typeof __VLS_components.elMenu | typeof __VLS_components.ElMenu | typeof __VLS_components['el-menu'] | typeof __VLS_components.elMenu | typeof __VLS_components.ElMenu | typeof __VLS_components['el-menu']} */
    elMenu;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        router: true,
        defaultActive: (__VLS_ctx.$route.path),
        ...{ class: "menu" },
    }));
    const __VLS_21 = __VLS_20({
        router: true,
        defaultActive: (__VLS_ctx.$route.path),
        ...{ class: "menu" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    /** @type {__VLS_StyleScopedClasses['menu']} */ ;
    const { default: __VLS_24 } = __VLS_22.slots;
    let __VLS_25;
    /** @ts-ignore @type { | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item'] | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item']} */
    elMenuItem;
    // @ts-ignore
    const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
        index: "/",
    }));
    const __VLS_27 = __VLS_26({
        index: "/",
    }, ...__VLS_functionalComponentArgsRest(__VLS_26));
    const { default: __VLS_30 } = __VLS_28.slots;
    // @ts-ignore
    [token, $route,];
    var __VLS_28;
    if (__VLS_ctx.role !== 'viewer') {
        let __VLS_31;
        /** @ts-ignore @type { | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item'] | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item']} */
        elMenuItem;
        // @ts-ignore
        const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
            index: "/chat",
        }));
        const __VLS_33 = __VLS_32({
            index: "/chat",
        }, ...__VLS_functionalComponentArgsRest(__VLS_32));
        const { default: __VLS_36 } = __VLS_34.slots;
        // @ts-ignore
        [role,];
        var __VLS_34;
    }
    let __VLS_37;
    /** @ts-ignore @type { | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item'] | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item']} */
    elMenuItem;
    // @ts-ignore
    const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
        index: "/agents",
    }));
    const __VLS_39 = __VLS_38({
        index: "/agents",
    }, ...__VLS_functionalComponentArgsRest(__VLS_38));
    const { default: __VLS_42 } = __VLS_40.slots;
    // @ts-ignore
    [];
    var __VLS_40;
    if (__VLS_ctx.role !== 'viewer') {
        let __VLS_43;
        /** @ts-ignore @type { | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item'] | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item']} */
        elMenuItem;
        // @ts-ignore
        const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
            index: "/knowledge",
        }));
        const __VLS_45 = __VLS_44({
            index: "/knowledge",
        }, ...__VLS_functionalComponentArgsRest(__VLS_44));
        const { default: __VLS_48 } = __VLS_46.slots;
        // @ts-ignore
        [role,];
        var __VLS_46;
    }
    let __VLS_49;
    /** @ts-ignore @type { | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item'] | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item']} */
    elMenuItem;
    // @ts-ignore
    const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
        index: "/tasks",
    }));
    const __VLS_51 = __VLS_50({
        index: "/tasks",
    }, ...__VLS_functionalComponentArgsRest(__VLS_50));
    const { default: __VLS_54 } = __VLS_52.slots;
    // @ts-ignore
    [];
    var __VLS_52;
    if (__VLS_ctx.role === 'admin') {
        let __VLS_55;
        /** @ts-ignore @type { | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item'] | typeof __VLS_components.elMenuItem | typeof __VLS_components.ElMenuItem | typeof __VLS_components['el-menu-item']} */
        elMenuItem;
        // @ts-ignore
        const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({
            index: "/audit",
        }));
        const __VLS_57 = __VLS_56({
            index: "/audit",
        }, ...__VLS_functionalComponentArgsRest(__VLS_56));
        const { default: __VLS_60 } = __VLS_58.slots;
        // @ts-ignore
        [role,];
        var __VLS_58;
    }
    // @ts-ignore
    [];
    var __VLS_22;
    // @ts-ignore
    [];
    var __VLS_16;
    let __VLS_61;
    /** @ts-ignore @type { | typeof __VLS_components.elContainer | typeof __VLS_components.ElContainer | typeof __VLS_components['el-container'] | typeof __VLS_components.elContainer | typeof __VLS_components.ElContainer | typeof __VLS_components['el-container']} */
    elContainer;
    // @ts-ignore
    const __VLS_62 = __VLS_asFunctionalComponent1(__VLS_61, new __VLS_61({}));
    const __VLS_63 = __VLS_62({}, ...__VLS_functionalComponentArgsRest(__VLS_62));
    const { default: __VLS_66 } = __VLS_64.slots;
    let __VLS_67;
    /** @ts-ignore @type { | typeof __VLS_components.elHeader | typeof __VLS_components.ElHeader | typeof __VLS_components['el-header'] | typeof __VLS_components.elHeader | typeof __VLS_components.ElHeader | typeof __VLS_components['el-header']} */
    elHeader;
    // @ts-ignore
    const __VLS_68 = __VLS_asFunctionalComponent1(__VLS_67, new __VLS_67({
        ...{ class: "header" },
    }));
    const __VLS_69 = __VLS_68({
        ...{ class: "header" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_68));
    /** @type {__VLS_StyleScopedClasses['header']} */ ;
    const { default: __VLS_72 } = __VLS_70.slots;
    let __VLS_73;
    /** @ts-ignore @type { | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button'] | typeof __VLS_components.elButton | typeof __VLS_components.ElButton | typeof __VLS_components['el-button']} */
    elButton;
    // @ts-ignore
    const __VLS_74 = __VLS_asFunctionalComponent1(__VLS_73, new __VLS_73({
        ...{ 'onClick': {} },
    }));
    const __VLS_75 = __VLS_74({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_74));
    let __VLS_78;
    const __VLS_79 = {
        /** @type {typeof __VLS_78.click} */
        onClick: (__VLS_ctx.exit),
    };
    const { default: __VLS_80 } = __VLS_76.slots;
    // @ts-ignore
    [exit,];
    var __VLS_76;
    var __VLS_77;
    // @ts-ignore
    [];
    var __VLS_70;
    let __VLS_81;
    /** @ts-ignore @type { | typeof __VLS_components.elMain | typeof __VLS_components.ElMain | typeof __VLS_components['el-main'] | typeof __VLS_components.elMain | typeof __VLS_components.ElMain | typeof __VLS_components['el-main']} */
    elMain;
    // @ts-ignore
    const __VLS_82 = __VLS_asFunctionalComponent1(__VLS_81, new __VLS_81({}));
    const __VLS_83 = __VLS_82({}, ...__VLS_functionalComponentArgsRest(__VLS_82));
    const { default: __VLS_86 } = __VLS_84.slots;
    let __VLS_87;
    /** @ts-ignore @type { | typeof __VLS_components.routerView | typeof __VLS_components.RouterView | typeof __VLS_components['router-view']} */
    routerView;
    // @ts-ignore
    const __VLS_88 = __VLS_asFunctionalComponent1(__VLS_87, new __VLS_87({}));
    const __VLS_89 = __VLS_88({}, ...__VLS_functionalComponentArgsRest(__VLS_88));
    // @ts-ignore
    [];
    var __VLS_84;
    // @ts-ignore
    [];
    var __VLS_64;
    // @ts-ignore
    [];
    var __VLS_9;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
