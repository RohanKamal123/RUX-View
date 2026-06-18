package com.visionos.app

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument

sealed class Screen(val route: String, val title: String, val icon: ImageVector) {
    object Cameras : Screen("cameras", "Cameras", Icons.Default.Videocam)
    object Events : Screen("events", "Events", Icons.Default.List)
    object Settings : Screen("settings", "Settings", Icons.Default.Settings)
}

sealed class DetailScreen(val route: String) {
    object EventDetail : DetailScreen("event_detail/{eventId}")
    object PersonProfile : DetailScreen("person_profile/{personUid}")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisionOSNavigation(
    api: VisionOSApi,
    onLogout: () -> Unit,
    onDeleteAccount: () -> Unit
) {
    val navController = rememberNavController()
    val bottomNavItems = listOf(Screen.Cameras, Screen.Events, Screen.Settings)

    Scaffold(
        bottomBar = {
            NavigationBar {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentDestination = navBackStackEntry?.destination

                bottomNavItems.forEach { screen ->
                    NavigationBarItem(
                        icon = { Icon(screen.icon, contentDescription = screen.title) },
                        label = { Text(screen.title) },
                        selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Cameras.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Cameras.route) {
                CameraListScreen(
                    cameras = remember { mutableStateListOf() },
                    onCameraTap = { cameraId ->
                        navController.navigate("events?cameraId=$cameraId")
                    },
                    onRefresh = { /* TODO: Refresh cameras from API */ }
                )
            }

            composable(Screen.Events.route) {
                EventFeedScreen(
                    cameraId = null,
                    events = remember { mutableStateListOf() },
                    onEventTap = { eventId ->
                        navController.navigate("event_detail/$eventId")
                    },
                    onRefresh = { /* TODO: Refresh events from API */ },
                    onLoadMore = { /* TODO: Load more events */ }
                )
            }

            composable(
                route = "events?cameraId={cameraId}",
                arguments = listOf(navArgument("cameraId") {
                    type = NavType.StringType
                    defaultValue = null
                    nullable = true
                })
            ) { backStackEntry ->
                val cameraId = backStackEntry.arguments?.getString("cameraId")
                EventFeedScreen(
                    cameraId = cameraId,
                    events = remember { mutableStateListOf() },
                    onEventTap = { eventId ->
                        navController.navigate("event_detail/$eventId")
                    },
                    onRefresh = { /* TODO: Refresh events from API */ },
                    onLoadMore = { /* TODO: Load more events */ }
                )
            }

            composable(
                route = DetailScreen.EventDetail.route,
                arguments = listOf(navArgument("eventId") { type = NavType.IntType })
            ) { backStackEntry ->
                val eventId = backStackEntry.arguments?.getInt("eventId") ?: return@composable
                EventDetailScreen(
                    eventId = eventId,
                    event = null,
                    onPersonTap = { personUid ->
                        navController.navigate("person_profile/$personUid")
                    },
                    onBack = { navController.popBackStack() }
                )
            }

            composable(
                route = DetailScreen.PersonProfile.route,
                arguments = listOf(navArgument("personUid") { type = NavType.StringType })
            ) { backStackEntry ->
                val personUid = backStackEntry.arguments?.getString("personUid") ?: return@composable
                PersonProfileScreen(
                    personUid = personUid,
                    profile = null,
                    onSightingTap = { eventId ->
                        navController.navigate("event_detail/$eventId")
                    },
                    onLabelEdit = { /* TODO: Update person label */ },
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.Settings.route) {
                SettingsScreen(
                    settings = AppSettings(
                        notificationsEnabled = true,
                        highAlertVibration = true,
                        emergencyAlertSound = true,
                        digestTime = "22:00",
                        theme = "system"
                    ),
                    onSettingChange = { key, value -> /* TODO: Update setting */ },
                    onLogout = onLogout,
                    onDeleteAccount = onDeleteAccount
                )
            }
        }
    }
}
