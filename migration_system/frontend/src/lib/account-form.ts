/** UI validation mirrors AccountService; the server remains authoritative. */
export interface AccountDraft {username:string;display_name:string;password:string;role:string}
export type AccountField = keyof AccountDraft
export function validateAccountDraft(form:AccountDraft):Record<AccountField,string> {
  return {
    username:!form.username?'请填写登录账号。':form.username.trim()!==form.username||!/^[A-Za-z][A-Za-z0-9_.-]{2,63}$/.test(form.username)?'账号须以英文字母开头，3–64 位；仅可使用字母、数字、下划线、点或横线，不能含中文或空格。':'',
    display_name:!form.display_name.trim()?'请填写显示名称，例如“张三”。':Array.from(form.display_name.trim()).length>120?'显示名称不能超过 120 个字符。':'',
    password:!form.password?'请设置临时密码，再单独告知用户。':Array.from(form.password).length<12||Array.from(form.password).length>128?'临时密码须为 12–128 个字符。':'',
    role:['user','admin'].includes(form.role)?'':'请选择普通用户或管理员。',
  }
}
