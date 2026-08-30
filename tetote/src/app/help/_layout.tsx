import { Tabs } from "expo-router";
import {
  View,
  Text,
  StyleSheet,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

type TabIconProps = {
  focused: boolean;
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
};

function TabIcon({
  focused,
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
          paddingTop: 8,
          paddingBottom: 7,
          width: "100%",
          maxWidth: 520,
          alignSelf: "center",
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "ホーム",
          tabBarIcon: ({ focused }) => (
            <TabIcon
              focused={focused}
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
              focused={focused}
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
        options={{
          href: null,
        }}
      />

      <Tabs.Screen
        name="character"
        options={{
          href: null,
        }}
      />

      <Tabs.Screen
        name="profile"
        options={{
          href: null,
        }}
      />

      <Tabs.Screen
        name="request"
        options={{
          href: null,
        }}
      />

      <Tabs.Screen
        name="settings"
        options={{
          href: null,
        }}
      />

      <Tabs.Screen
        name="request-manual"
        options={{
          href: null,
        }}
      />

      <Tabs.Screen
        name="request-voice"
        options={{
          href: null,
        }}
      />

      <Tabs.Screen
        name="request-confirm"
        options={{
          href: null,
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabItem: {
    alignItems: "center",
    justifyContent: "center",
    minWidth: 90,
    height: 65,
  },

  tabLabel: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800",
    marginTop: 4,
  },
});
