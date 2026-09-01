---
name: manual-runner-config
description: 为 Vue/San 成对组件配置两个人工测试页面，只修改指定的组件配置代码块；当组件需要接入 tests/manual/vue-test-runner.html 和 tests/manual/san-test-runner.html，并由用户人工测试时使用。
---

# 人工测试页面配置

当用户要求将已有的 Vue/San 成对组件接入仓库的人工测试页面时，使用此技能。更新两个测试页面中的组件配置代码块后，任务即告完成。测试由用户人工执行，因此除非用户另行要求，否则不要启动服务器、打开浏览器或运行测试命令。

## 允许修改的文件和代码块

只能修改以下文件：

- `tests/manual/san-test-runner.html`
- `tests/manual/vue-test-runner.html`

在 San 测试页面中，只修改以下对象的内容：

```js
const TEST_CONFIG = {
    componentPath: '',
    componentTag: '',
    props: {
    }
};
```

在 Vue 测试页面中，只修改现有 `#app` / `new Vue` 代码块内的组件标签和组件注册配置：

```html
<div id="app">
    <!-- 在这里测试组件 -->
    <component-tag></component-tag>
</div>
<script>
    new Vue({
        el: '#app',
        components: {
            'component-tag': httpVueLoader('relative/path/to/Component.vue'),
        }
    });
</script>
```

保留周围的 HTML、CDN 引用、San 加载器实现、Vue 初始化结构、注释和错误处理。不要修改组件源文件、数据集元数据、`tests/manual/test-page.html` 或任何其他文件。

## 配置规则

1. 两个组件路径都必须以 `tests/manual/` 为基准计算相对路径。
   - San 的 `componentPath` 指向成对组件中的 `.san` 文件。
   - Vue 的 `httpVueLoader(...)` 指向成对组件中的 `.vue` 文件。
2. `componentTag` 和 Vue 组件注册键必须使用相同的 kebab-case 标签，并与加载的组件一致，例如 `focus-card`。
3. 只将组件已声明的 props 写入 `TEST_CONFIG.props`。
   - San 中保持 JavaScript 值的真实类型：`25`、`true`、数组和对象不能改成字符串。
   - Vue 标签中，字符串使用普通引号属性；数字、布尔值、数组、对象或表达式使用 `:` 绑定。
   - 组件未声明 props 时保持 `props` 为空，不要虚构测试数据。
4. Vue 2 在此页面中使用 HTML DOM 模板，因此自定义组件必须使用显式闭合标签：`<component-tag></component-tag>`。
5. 两个测试页面的配置必须等价：组件身份相同，props 值及类型对应一致。

## 完成检查

修改后检查差异，确认只有上述两个允许修改的代码块发生变化。汇报已配置的路径、标签和 props。不要声称组件已成功渲染或交互测试已通过，这些检查明确交由用户人工完成。
