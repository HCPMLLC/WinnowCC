# PROMPT 40: Mobile App (Expo / React Native)

## Objective
Build cross-platform mobile apps (iOS & Android) using Expo and React Native that provide core Winnow functionality for both candidates and employers. Focus on job matching, application tracking, and candidate search on mobile devices.

---

## Context
Your web app is desktop-first, but users want mobile access for:
- **Candidates**: Browse jobs on the go, quick apply, track applications
- **Employers**: Review candidates anywhere, manage jobs, get notifications

We'll use **Expo** (not plain React Native) for easier development and deployment.

---

## Prerequisites
- ✅ Backend API complete (PROMPT36+)
- ✅ Web app working
- ✅ Node.js installed
- ✅ iOS Simulator (Mac) or Android Studio (optional for testing)

---

## Technology Stack

- **Expo**: React Native framework for easier development
- **React Navigation**: Routing and navigation
- **Expo SecureStore**: Secure token storage
- **Expo Notifications**: Push notifications
- **NativeWind**: Tailwind for React Native

---

## Setup Steps

### Step 0: Install Expo CLI

**Terminal Commands:**
```bash
# Install Expo CLI globally
npm install -g expo-cli

# Or use npx (no global install needed)
# We'll use npx in the commands below
```

---

### Step 1: Create Expo Project

**Location:** Root of your monorepo

**Commands:**
```bash
# From project root (where web/ and services/ are)
npx create-expo-app mobile --template blank-typescript

# Move into mobile directory
cd mobile

# Install dependencies
npm install @react-navigation/native @react-navigation/native-stack @react-navigation/bottom-tabs
npm install react-native-screens react-native-safe-area-context
npm install expo-secure-store expo-notifications
npm install nativewind
npm install --save-dev tailwindcss
```

---

### Step 2: Configure NativeWind (Tailwind for React Native)

**Location:** `mobile/tailwind.config.js`

**Create file:**
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./App.{js,jsx,ts,tsx}",
    "./src/**/*.{js,jsx,ts,tsx}"
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

**Location:** `mobile/babel.config.js`

**Update:**
```javascript
module.exports = function(api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: ["nativewind/babel"],
  };
};
```

---

### Step 3: Project Structure

**Location:** Create these folders in `mobile/`

```bash
cd mobile
mkdir -p src/{screens,components,navigation,services,contexts,types}
```

**Structure:**
```
mobile/
├── src/
│   ├── screens/          # All screen components
│   │   ├── auth/
│   │   ├── candidate/
│   │   └── employer/
│   ├── components/       # Reusable UI components
│   ├── navigation/       # Navigation setup
│   ├── services/         # API calls
│   ├── contexts/         # Auth context, etc.
│   └── types/           # TypeScript types
├── App.tsx
└── package.json
```

---

### Step 4: API Service

**Location:** Create `mobile/src/services/api.ts`

**Code:**
```typescript
import * as SecureStore from 'expo-secure-store';

const API_URL = __DEV__ 
  ? 'http://localhost:8000'  // Development
  : 'https://api.winnow.com'; // Production

// Token management
export async function getToken(): Promise<string | null> {
  return await SecureStore.getItemAsync('accessToken');
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync('accessToken', token);
}

export async function removeToken(): Promise<void> {
  await SecureStore.deleteItemAsync('accessToken');
}

// API helper
async function apiRequest(
  endpoint: string,
  options: RequestInit = {}
): Promise<any> {
  const token = await getToken();
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Request failed');
  }
  
  return response.json();
}

// Auth API
export const authAPI = {
  async login(email: string, password: string) {
    const data = await apiRequest('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    
    await setToken(data.access_token);
    return data;
  },
  
  async signup(email: string, password: string, role: 'candidate' | 'employer') {
    return apiRequest('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password, role }),
    });
  },
  
  async getCurrentUser() {
    return apiRequest('/api/auth/me');
  },
  
  async logout() {
    await removeToken();
  },
};

// Candidate API
export const candidateAPI = {
  async getMatches() {
    return apiRequest('/api/candidate/matches');
  },
  
  async getProfile() {
    return apiRequest('/api/candidate/profile');
  },
  
  async getApplications() {
    return apiRequest('/api/candidate/applications');
  },
};

// Employer API
export const employerAPI = {
  async getJobs() {
    return apiRequest('/api/employer/jobs');
  },
  
  async createJob(jobData: any) {
    return apiRequest('/api/employer/jobs', {
      method: 'POST',
      body: JSON.stringify(jobData),
    });
  },
  
  async searchCandidates(filters: any) {
    return apiRequest('/api/employer/candidates/search', {
      method: 'POST',
      body: JSON.stringify(filters),
    });
  },
  
  async getAnalytics() {
    return apiRequest('/api/employer/analytics/summary');
  },
};
```

---

### Step 5: Auth Context

**Location:** Create `mobile/src/contexts/AuthContext.tsx`

**Code:**
```typescript
import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { authAPI } from '../services/api';

interface User {
  id: string;
  email: string;
  role: 'candidate' | 'employer' | 'both';
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, role: 'candidate' | 'employer') => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      const userData = await authAPI.getCurrentUser();
      setUser(userData);
    } catch (error) {
      console.log('Not authenticated');
    } finally {
      setIsLoading(false);
    }
  }

  async function login(email: string, password: string) {
    await authAPI.login(email, password);
    const userData = await authAPI.getCurrentUser();
    setUser(userData);
  }

  async function signup(email: string, password: string, role: 'candidate' | 'employer') {
    await authAPI.signup(email, password, role);
    await login(email, password);
  }

  async function logout() {
    await authAPI.logout();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
```

---

### Step 6: Navigation Setup

**Location:** Create `mobile/src/navigation/AppNavigator.tsx`

**Code:**
```typescript
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useAuth } from '../contexts/AuthContext';

// Auth Screens
import LoginScreen from '../screens/auth/LoginScreen';
import SignupScreen from '../screens/auth/SignupScreen';

// Candidate Screens
import CandidateHomeScreen from '../screens/candidate/HomeScreen';
import JobMatchesScreen from '../screens/candidate/JobMatchesScreen';
import ApplicationsScreen from '../screens/candidate/ApplicationsScreen';
import ProfileScreen from '../screens/candidate/ProfileScreen';

// Employer Screens
import EmployerHomeScreen from '../screens/employer/HomeScreen';
import JobsScreen from '../screens/employer/JobsScreen';
import CandidatesScreen from '../screens/employer/CandidatesScreen';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function CandidateTabs() {
  return (
    <Tab.Navigator>
      <Tab.Screen name="Home" component={CandidateHomeScreen} />
      <Tab.Screen name="Matches" component={JobMatchesScreen} />
      <Tab.Screen name="Applications" component={ApplicationsScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

function EmployerTabs() {
  return (
    <Tab.Navigator>
      <Tab.Screen name="Home" component={EmployerHomeScreen} />
      <Tab.Screen name="Jobs" component={JobsScreen} />
      <Tab.Screen name="Candidates" component={CandidatesScreen} />
    </Tab.Navigator>
  );
}

export default function AppNavigator() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return null; // Or loading screen
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!user ? (
          // Auth Stack
          <>
            <Stack.Screen name="Login" component={LoginScreen} />
            <Stack.Screen name="Signup" component={SignupScreen} />
          </>
        ) : user.role === 'candidate' || user.role === 'both' ? (
          // Candidate App
          <Stack.Screen name="CandidateApp" component={CandidateTabs} />
        ) : (
          // Employer App
          <Stack.Screen name="EmployerApp" component={EmployerTabs} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
```

---

### Step 7: Sample Screens

**Location:** Create `mobile/src/screens/auth/LoginScreen.tsx`

**Code:**
```typescript
import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Alert } from 'react-native';
import { useAuth } from '../../contexts/AuthContext';

export default function LoginScreen({ navigation }: any) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  async function handleLogin() {
    if (!email || !password) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    setIsLoading(true);
    try {
      await login(email, password);
    } catch (error: any) {
      Alert.alert('Login Failed', error.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <View className="flex-1 bg-white px-6 justify-center">
      <Text className="text-3xl font-bold mb-8 text-center">Welcome to Winnow</Text>

      <TextInput
        className="border border-gray-300 rounded-lg px-4 py-3 mb-4"
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
      />

      <TextInput
        className="border border-gray-300 rounded-lg px-4 py-3 mb-6"
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />

      <TouchableOpacity
        className="bg-blue-600 rounded-lg py-4 mb-4"
        onPress={handleLogin}
        disabled={isLoading}
      >
        <Text className="text-white text-center font-semibold text-lg">
          {isLoading ? 'Logging in...' : 'Log In'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity onPress={() => navigation.navigate('Signup')}>
        <Text className="text-blue-600 text-center">
          Don't have an account? Sign up
        </Text>
      </TouchableOpacity>
    </View>
  );
}
```

**Location:** Create `mobile/src/screens/candidate/HomeScreen.tsx`

**Code:**
```typescript
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, RefreshControl } from 'react-native';
import { candidateAPI } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';

export default function CandidateHomeScreen({ navigation }: any) {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    try {
      const profile = await candidateAPI.getProfile();
      const matches = await candidateAPI.getMatches();
      const applications = await candidateAPI.getApplications();

      setStats({
        profileCompleteness: profile.completeness_score || 0,
        totalMatches: matches.length,
        activeApplications: applications.filter((a: any) => 
          a.status === 'applied' || a.status === 'interviewing'
        ).length,
      });
    } catch (error) {
      console.error('Failed to fetch data:', error);
    }
  }

  async function onRefresh() {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }

  return (
    <ScrollView
      className="flex-1 bg-gray-50"
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <View className="bg-blue-600 px-6 pt-12 pb-8">
        <Text className="text-white text-2xl font-bold mb-2">
          Welcome back!
        </Text>
        <Text className="text-blue-100">{user?.email}</Text>
      </View>

      <View className="px-6 py-6">
        {/* Stats Grid */}
        <View className="flex-row justify-between mb-6">
          <StatCard
            title="Profile"
            value={`${stats?.profileCompleteness || 0}%`}
            icon="✓"
          />
          <StatCard
            title="Matches"
            value={stats?.totalMatches || 0}
            icon="🎯"
          />
          <StatCard
            title="Active"
            value={stats?.activeApplications || 0}
            icon="📨"
          />
        </View>

        {/* Quick Actions */}
        <Text className="text-lg font-semibold mb-4">Quick Actions</Text>
        
        <TouchableOpacity
          className="bg-white rounded-lg p-4 mb-3 shadow-sm"
          onPress={() => navigation.navigate('Matches')}
        >
          <Text className="font-semibold text-gray-900 mb-1">
            Browse Job Matches
          </Text>
          <Text className="text-sm text-gray-600">
            See jobs tailored to your profile
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          className="bg-white rounded-lg p-4 mb-3 shadow-sm"
          onPress={() => navigation.navigate('Applications')}
        >
          <Text className="font-semibold text-gray-900 mb-1">
            Track Applications
          </Text>
          <Text className="text-sm text-gray-600">
            Monitor your application status
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          className="bg-white rounded-lg p-4 mb-3 shadow-sm"
          onPress={() => navigation.navigate('Profile')}
        >
          <Text className="font-semibold text-gray-900 mb-1">
            Update Profile
          </Text>
          <Text className="text-sm text-gray-600">
            Keep your information current
          </Text>
        </TouchableOpacity>

        {/* Logout */}
        <TouchableOpacity
          className="mt-6"
          onPress={logout}
        >
          <Text className="text-red-600 text-center">Log Out</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

function StatCard({ title, value, icon }: any) {
  return (
    <View className="bg-white rounded-lg p-4 flex-1 mx-1 shadow-sm">
      <Text className="text-2xl mb-1">{icon}</Text>
      <Text className="text-2xl font-bold text-gray-900">{value}</Text>
      <Text className="text-xs text-gray-600">{title}</Text>
    </View>
  );
}
```

---

### Step 8: Main App File

**Location:** `mobile/App.tsx`

**Code:**
```typescript
import { StatusBar } from 'expo-status-bar';
import { AuthProvider } from './src/contexts/AuthContext';
import AppNavigator from './src/navigation/AppNavigator';

export default function App() {
  return (
    <AuthProvider>
      <AppNavigator />
      <StatusBar style="auto" />
    </AuthProvider>
  );
}
```

---

### Step 9: Configure app.json

**Location:** `mobile/app.json`

**Update:**
```json
{
  "expo": {
    "name": "Winnow",
    "slug": "winnow",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "light",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#2563eb"
    },
    "assetBundlePatterns": [
      "**/*"
    ],
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.winnow.app"
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#2563eb"
      },
      "package": "com.winnow.app"
    },
    "web": {
      "favicon": "./assets/favicon.png"
    },
    "extra": {
      "eas": {
        "projectId": "your-project-id"
      }
    }
  }
}
```

---

## Running the App

### Development

**Terminal Commands:**
```bash
cd mobile

# Start Expo development server
npx expo start

# Then choose:
# - Press 'i' for iOS simulator (Mac only)
# - Press 'a' for Android emulator
# - Scan QR code with Expo Go app on physical device
```

**Install Expo Go on your phone:**
- iOS: https://apps.apple.com/app/expo-go/id982107779
- Android: https://play.google.com/store/apps/details?id=host.exp.exponent

---

## Building for Production

### Step 10: Install EAS CLI

```bash
npm install -g eas-cli
```

### Step 11: Configure EAS Build

```bash
cd mobile
eas login
eas build:configure
```

### Step 12: Build App

**For iOS:**
```bash
# Build for App Store
eas build --platform ios

# Build for TestFlight
eas build --platform ios --profile preview
```

**For Android:**
```bash
# Build APK for testing
eas build --platform android --profile preview

# Build AAB for Play Store
eas build --platform android
```

---

## Push Notifications Setup

### Step 13: Configure Notifications

**Location:** `mobile/src/services/notifications.ts`

**Code:**
```typescript
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotificationsAsync() {
  let token;

  if (Device.isDevice) {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;
    
    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    
    if (finalStatus !== 'granted') {
      alert('Failed to get push token for push notification!');
      return;
    }
    
    token = (await Notifications.getExpoPushTokenAsync()).data;
  } else {
    alert('Must use physical device for Push Notifications');
  }

  if (Platform.OS === 'android') {
    Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#FF231F7C',
    });
  }

  return token;
}
```

---

## Additional Screens to Implement

Create these screens following the same patterns:

### Candidate Screens
1. **JobMatchesScreen** - List of matched jobs with filters
2. **JobDetailScreen** - Job details with apply button
3. **ApplicationsScreen** - Track application status
4. **ProfileScreen** - View/edit candidate profile

### Employer Screens
1. **JobsScreen** - List employer's job postings
2. **CreateJobScreen** - Create new job posting
3. **CandidatesScreen** - Search and browse candidates
4. **CandidateDetailScreen** - View candidate profile
5. **AnalyticsScreen** - Dashboard with stats

---

## Testing Checklist

After implementation:

✅ Can login on mobile device  
✅ Can signup with role selection  
✅ Candidate home screen shows stats  
✅ Can view job matches  
✅ Can apply to jobs  
✅ Can track applications  
✅ Employer can view jobs  
✅ Employer can search candidates  
✅ Push notifications work (physical device)  
✅ Token persists after app restart  
✅ Logout clears token  

---

## Troubleshooting

### "Unable to resolve module" errors
**Cause:** Missing dependencies  
**Solution:** Run `npm install` and restart Expo

### API calls fail with network error
**Cause:** Wrong API URL or localhost not accessible  
**Solution:** Use your computer's IP address instead of localhost (e.g., `http://192.168.1.100:8000`)

### iOS build fails
**Cause:** Missing certificates  
**Solution:** Run `eas credentials` to set up certificates

### App crashes on launch
**Cause:** Usually auth context issue  
**Solution:** Check that SecureStore is working, clear app data

---

## Next Steps

After completing this prompt:

1. **PROMPT41:** Production Deployment (Cloud Run, Cloud SQL)
2. **PROMPT42:** Advanced Matching Algorithm
3. **App Store Submission** (iOS & Android)

---

## Success Criteria

✅ Mobile app runs in Expo Go  
✅ Auth flow works (login/signup)  
✅ Candidate can view matches  
✅ Candidate can track applications  
✅ Employer can view jobs  
✅ Employer can search candidates  
✅ API calls work on physical device  
✅ Tailwind styles render correctly  
✅ Can build production app with EAS  

---

**Status:** Ready for implementation  
**Estimated Time:** 6-8 hours (for basic version)  
**Dependencies:** PROMPT36 (backend API working)  
**Next Prompt:** PROMPT41_Production_Deployment.md
