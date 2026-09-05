// CSS の import を TypeScript に教える宣言。
// ローカルでは `expo start` / `expo export` が .expo/types に同等の宣言を生成するため
// 気づきにくいが、CI のようなクリーンな環境では tsc がこれ無しに失敗する。
declare module "*.module.css" {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare module "*.css";
