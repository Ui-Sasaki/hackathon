# Welcome to your Expo app 👋

This is an [Expo](https://expo.dev) project created with [`create-expo-app`](https://www.npmjs.com/package/create-expo-app).

## Get started

1. Install dependencies

   ```bash
   npm install
   ```

2. Start the app

   ```bash
   npx expo start
   ```

In the output, you'll find options to open the app in a

- [development build](https://docs.expo.dev/develop/development-builds/introduction/)
- [Android emulator](https://docs.expo.dev/workflow/android-studio-emulator/)
- [iOS simulator](https://docs.expo.dev/workflow/ios-simulator/)
- [Expo Go](https://expo.dev/go), a limited sandbox for trying out app development with Expo

You can start developing by editing the files inside the **app** directory. This project uses [file-based routing](https://docs.expo.dev/router/introduction).

## Get a fresh project

When you're ready, run:

```bash
npm run reset-project
```

This command will move the starter code to the **app-example** directory and create a blank **app** directory where you can start developing.

### Other setup steps

- To set up ESLint for linting, run `npx expo lint`, or follow our guide on ["Using ESLint and Prettier"](https://docs.expo.dev/guides/using-eslint/)
- If you'd like to set up unit testing, follow our guide on ["Unit Testing with Jest"](https://docs.expo.dev/develop/unit-testing/)
- Learn more about the TypeScript setup in this template in our guide on ["Using TypeScript"](https://docs.expo.dev/guides/typescript/)

## Learn more

To learn more about developing your project with Expo, look at the following resources:

- [Expo documentation](https://docs.expo.dev/): Learn fundamentals, or go into advanced topics with our [guides](https://docs.expo.dev/guides).
- [Learn Expo tutorial](https://docs.expo.dev/tutorial/introduction/): Follow a step-by-step tutorial where you'll create a project that runs on Android, iOS, and the web.

## Join the community

Join our community of developers creating universal apps.

- [Expo on GitHub](https://github.com/expo/expo): View our open source platform and contribute.
- [Discord community](https://chat.expo.dev): Chat with Expo users and ask questions.

## 認証のローカル確認

FastAPI と SuperTokens Core を起動し、フロントのAPI URLを指定してWeb版を起動する。

```bash
EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web
```

FastAPI側は `WEBSITE_DOMAIN` を実際のフロントOrigin（既定は
`http://localhost:3000`）に一致させる。ローカルHTTPでのみ
`AUTH_COOKIE_SECURE=false` を使い、Preview・本番はHTTPS、Secure Cookieを必須とする。

Chrome、Safari、Edgeの開発者ツールで次を確認する。

- 登録・ログイン後にHttpOnlyのセッションCookieが発行され、再読み込み後も復元される
- API通信が `credentials: include` で行われ、SuperTokens SDKがanti-CSRFヘッダーを付与する
- CookieのSameSite設定がフロント/APIの配置に合い、本番CookieにSecure属性がある
- ログアウト後または期限切れ後に保護画面へ戻れず、ログイン画面へ1回だけ遷移する
- パスワード、Cookie、セッショントークン、anti-CSRF値がURL・Storage・ログへ出ない

認証テストは `npm test`、静的検査は `npm run lint`、Web成果物は
`npx expo export --platform web` で確認する。
