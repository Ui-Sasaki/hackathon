import { Tabs } from "expo-router";
import {
  View,
  Text,
  StyleSheet,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useMode } from "../../context/ModeContext";
import HelpIcon from "../../../assets/home/helpicon.svg";

type TabIconProps = {
  focused: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
  label: string;
  special?: boolean;
  profile?: boolean;
};

function TabIcon({
  focused,
  icon,
  label,
  special = false,
  profile = false,
}: TabIconProps) {
  if (special) {
    return (
      <View style={styles.tabItem}>
        <View style={styles.iconContainer}>
          <HelpIcon
            width={50}
            height={50}
          />
        </View>

        <Text style={styles.tabLabel}>
          {label}
        </Text>
      </View>
    );
  }

  if (profile) {
    return (
      <View style={styles.tabItem}>
        <View
          style={[
            styles.profileCircle,
            focused &&
              styles.profileCircleFocused,
          ]}
        />

        <Text style={styles.tabLabel}>
          {label}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.tabItem}>
      <View style={styles.iconContainer}>
        {icon && (
          <Ionicons
            name={icon}
            size={28}
            color={
              focused
                ? "#F2A329"
                : "#FFF5E9"
            }
          />
        )}
      </View>

      <Text
        style={[
          styles.tabLabel,
          focused &&
            styles.tabLabelFocused,
        ]}
      >
        {label}
      </Text>
    </View>
  );
}

export default function TabLayout() {
  const { mode } = useMode();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,

        tabBarStyle: {
          height: 84,
          backgroundColor: "#1F572A",
          borderTopWidth: 0,
          paddingTop: 7,
          paddingBottom: 6,
          width: "100%",
          maxWidth: 520,
          alignSelf: "center",
          overflow: "visible",
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "求人",

          tabBarIcon: ({ focused }) => (
            <TabIcon
              focused={focused}
              icon={
                focused
                  ? "briefcase"
                  : "briefcase-outline"
              }
              label="求人"
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
        name="request"
        options={{
          href:
            mode === "requester"
              ? undefined
              : null,

          title: "お願いする",

          tabBarIcon: ({ focused }) => (
            <TabIcon
              focused={focused}
              label="お願いする"
              special
            />
          ),
        }}
      />

      <Tabs.Screen
        name="character"
        options={{
          title: "キャラクター",

          tabBarIcon: ({ focused }) => (
            <TabIcon
              focused={focused}
              icon={
                focused
                  ? "happy"
                  : "happy-outline"
              }
              label="キャラクター"
            />
          ),
        }}
      />

      <Tabs.Screen
        name="profile"
        options={{
          title: "プロフィール",

          tabBarIcon: ({ focused }) => (
            <TabIcon
              focused={focused}
              label="プロフィール"
              profile
            />
          ),
        }}
      />

      <Tabs.Screen
        name="saved"
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
    minWidth: 62,
    height: 68,
  },

  iconContainer: {
    width: 46,
    height: 43,
    alignItems: "center",
    justifyContent: "center",
  },

  tabLabel: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "700",
    marginTop: 1,
  },

  tabLabelFocused: {
    color: "#F2A329",
  },

  profileCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "#35410F",
  },

  profileCircleFocused: {
    borderWidth: 3,
    borderColor: "#F2A329",
  },
});