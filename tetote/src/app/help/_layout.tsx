import { Tabs } from "expo-router";
import {
  View,
  Text,
  StyleSheet,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

type TabIconProps = {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
};

function TabIcon({
  icon,
  label,
}: TabIconProps) {
  return (
    <View style={styles.tabItem}>
      <Ionicons
        name={icon}
        size={28}
        color="#FFFFFF"
      />

      <Text style={styles.tabLabel}>
        {label}
      </Text>
    </View>
  );
}

// href: null だけでタブバーから消える。tabBarButton を併用すると expo-router が
// 「Cannot use `href` and `tabBarButton` together」を投げ、依頼者側の全画面が真っ白になる。
const hiddenTabOptions = {
  href: null,
  tabBarItemStyle: {
    display: "none" as const,
  },
};

export default function HelpLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: {
          height: 82,
          backgroundColor: "#E6AA47",
          borderTopWidth: 0,
          paddingTop: 12,
          paddingBottom: 2,
          width: "100%",
          maxWidth: 520,
          alignSelf: "center",
        },
        tabBarItemStyle: {
          height: 82,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "ホーム",
          tabBarIcon: ({ focused }) => (
            <TabIcon
              icon={
                focused
                  ? "home"
                  : "home-outline"
              }
              label="ホーム"
            />
          ),
        }}
      />

      <Tabs.Screen
        name="chats"
        options={{
          title: "トーク",
          tabBarIcon: ({ focused }) => (
            <TabIcon
              icon={
                focused
                  ? "chatbubble-ellipses"
                  : "chatbubble-ellipses-outline"
              }
              label="トーク"
            />
          ),
        }}
      />

      <Tabs.Screen
        name="chat"
        options={hiddenTabOptions}
      />

      <Tabs.Screen
        name="character"
        options={hiddenTabOptions}
      />

      <Tabs.Screen
        name="profile"
        options={hiddenTabOptions}
      />

      <Tabs.Screen
        name="request"
        options={hiddenTabOptions}
      />

      <Tabs.Screen
        name="settings"
        options={hiddenTabOptions}
      />

      <Tabs.Screen
        name="request-manual"
        options={hiddenTabOptions}
      />

      <Tabs.Screen
        name="request-voice"
        options={hiddenTabOptions}
      />

      <Tabs.Screen
        name="request-confirm"
        options={hiddenTabOptions}
      />
      <Tabs.Screen name="requests" options={{ href: null }} />
      <Tabs.Screen name="report" options={{ href: null }} />
      <Tabs.Screen name="verification" options={{ href: null }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabItem: {
    alignItems: "center",
    justifyContent: "center",
    minWidth: 90,
    height: 65,
    transform: [{ translateY: 5 }],
  },

  tabLabel: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800",
    marginTop: 4,
  },
});