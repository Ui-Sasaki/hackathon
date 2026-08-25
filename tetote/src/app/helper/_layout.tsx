import { Tabs } from "expo-router";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

type TabIconProps = {
  focused: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
  label: string;
  profile?: boolean;
};

function TabIcon({
  focused,
  icon,
  label,
  profile = false,
}: TabIconProps) {
  return (
    <View style={styles.tabItem}>
      {profile ? (
        <View
          style={[
            styles.profileCircle,
            focused && styles.profileCircleFocused,
          ]}
        >
          <Ionicons
            name="person"
            size={24}
            color={focused ? "#F2A329" : "#FFF5E9"}
          />
        </View>
      ) : (
        <View style={styles.iconContainer}>
          {icon && (
            <Ionicons
              name={icon}
              size={28}
              color={focused ? "#F2A329" : "#FFF5E9"}
            />
          )}
        </View>
      )}

      <Text
        style={[
          styles.tabLabel,
          focused && styles.tabLabelFocused,
        ]}
      >
        {label}
      </Text>
    </View>
  );
}

export default function HelperLayout() {
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
        },
      }}
    >
      {/* 求人 */}
      <Tabs.Screen
        name="index"
        options={{
          title: "求人",
          tabBarIcon: ({ focused }) => (
            <TabIcon
              focused={focused}
              icon={focused ? "briefcase" : "briefcase-outline"}
              label="求人"
            />
          ),
        }}
      />

      {/* トーク */}
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

      {/* キャラクター */}
      <Tabs.Screen
        name="character"
        options={{
          title: "キャラクター",
          tabBarIcon: ({ focused }) => (
            <TabIcon
              focused={focused}
              icon={focused ? "happy" : "happy-outline"}
              label="キャラクター"
            />
          ),
        }}
      />

      {/* プロフィール */}
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
  name="settings"
  options={{
    href: null,
  }}
/>

      {/* HIDDEN SCREENS */}
      <Tabs.Screen
        name="saved"
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
    alignItems: "center",
    justifyContent: "center",
  },

  profileCircleFocused: {
    borderWidth: 3,
    borderColor: "#F2A329",
  },
});