package com.visionos.app

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    settings: AppSettings,
    onSettingChange: (String, Any) -> Unit,
    onLogout: () -> Unit,
    onDeleteAccount: () -> Unit
) {
    var showLogoutConfirm by remember { mutableStateOf(false) }
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var showDigestPicker by remember { mutableStateOf(false) }
    var showThemeSelector by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Notification Preferences Section
            Text(
                text = "Notifications",
                fontWeight = FontWeight.SemiBold,
                fontSize = 18.sp,
                modifier = Modifier.padding(vertical = 8.dp)
            )

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    SettingToggle(
                        title = "Push Notifications",
                        description = "Receive alerts for camera events",
                        checked = settings.notificationsEnabled,
                        onCheckedChange = { onSettingChange("notificationsEnabled", it) }
                    )

                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

                    SettingToggle(
                        title = "High Alert Vibration",
                        description = "Vibrate on HIGH threat events",
                        checked = settings.highAlertVibration,
                        onCheckedChange = { onSettingChange("highAlertVibration", it) }
                    )

                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

                    SettingToggle(
                        title = "Emergency Alert Sound",
                        description = "Play sound on EMERGENCY events",
                        checked = settings.emergencyAlertSound,
                        onCheckedChange = { onSettingChange("emergencyAlertSound", it) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Digest time
            Text(
                text = "Daily Digest",
                fontWeight = FontWeight.SemiBold,
                fontSize = 18.sp,
                modifier = Modifier.padding(vertical = 8.dp)
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                onClick = { showDigestPicker = true }
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(text = "Digest Time", fontSize = 16.sp)
                        Text(
                            text = "Daily summary sent at ${settings.digestTime}",
                            fontSize = 14.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Text(
                        text = settings.digestTime,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Theme
            Text(
                text = "Appearance",
                fontWeight = FontWeight.SemiBold,
                fontSize = 18.sp,
                modifier = Modifier.padding(vertical = 8.dp)
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                onClick = { showThemeSelector = true }
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(text = "Theme", fontSize = 16.sp)
                        Text(
                            text = settings.theme.replaceFirstChar { it.uppercase() },
                            fontSize = 14.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Text(
                        text = settings.theme.replaceFirstChar { it.uppercase() },
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            // Account actions
            Button(
                onClick = { showLogoutConfirm = true },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error
                )
            ) {
                Icon(Icons.Default.Logout, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Logout")
            }

            OutlinedButton(
                onClick = { showDeleteConfirm = true },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = MaterialTheme.colorScheme.error
                )
            ) {
                Icon(Icons.Default.Delete, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Delete Account")
            }
        }
    }

    // Logout confirmation
    if (showLogoutConfirm) {
        AlertDialog(
            onDismissRequest = { showLogoutConfirm = false },
            title = { Text("Logout") },
            text = { Text("Are you sure you want to logout?") },
            confirmButton = {
                TextButton(onClick = {
                    showLogoutConfirm = false
                    onLogout()
                }) { Text("Logout") }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutConfirm = false }) { Text("Cancel") }
            }
        )
    }

    // Delete account confirmation
    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("Delete Account") },
            text = { Text("This action is irreversible. All your data will be permanently deleted. Are you sure?") },
            confirmButton = {
                TextButton(onClick = {
                    showDeleteConfirm = false
                    onDeleteAccount()
                }) { Text("Delete", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) { Text("Cancel") }
            }
        )
    }

    // Digest time picker dialog
    if (showDigestPicker) {
        var selectedHour by remember { mutableStateOf(settings.digestTime.substringBefore(":")) }
        var selectedMinute by remember { mutableStateOf(settings.digestTime.substringAfter(":")) }
        val hours = (0..23).map { String.format("%02d", it) }
        val minutes = listOf("00", "15", "30", "45")

        AlertDialog(
            onDismissRequest = { showDigestPicker = false },
            title = { Text("Select Digest Time") },
            text = {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Hour", fontSize = 14.sp)
                        hours.forEach { hour ->
                            TextButton(onClick = { selectedHour = hour }) {
                                Text(
                                    text = hour,
                                    fontWeight = if (hour == selectedHour) FontWeight.Bold else FontWeight.Normal,
                                    color = if (hour == selectedHour) MaterialTheme.colorScheme.primary
                                    else MaterialTheme.colorScheme.onSurface
                                )
                            }
                        }
                    }
                    Text(":", fontSize = 24.sp)
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Min", fontSize = 14.sp)
                        minutes.forEach { minute ->
                            TextButton(onClick = { selectedMinute = minute }) {
                                Text(
                                    text = minute,
                                    fontWeight = if (minute == selectedMinute) FontWeight.Bold else FontWeight.Normal,
                                    color = if (minute == selectedMinute) MaterialTheme.colorScheme.primary
                                    else MaterialTheme.colorScheme.onSurface
                                )
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    onSettingChange("digestTime", "$selectedHour:$selectedMinute")
                    showDigestPicker = false
                }) { Text("Save") }
            },
            dismissButton = {
                TextButton(onClick = { showDigestPicker = false }) { Text("Cancel") }
            }
        )
    }

    // Theme selector dialog
    if (showThemeSelector) {
        val themes = listOf("system", "light", "dark")
        AlertDialog(
            onDismissRequest = { showThemeSelector = false },
            title = { Text("Select Theme") },
            text = {
                Column {
                    themes.forEach { theme ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            RadioButton(
                                selected = settings.theme == theme,
                                onClick = {
                                    onSettingChange("theme", theme)
                                    showThemeSelector = false
                                }
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = theme.replaceFirstChar { it.uppercase() },
                                fontSize = 16.sp
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showThemeSelector = false }) { Text("Close") }
            }
        )
    }
}

@Composable
private fun SettingToggle(
    title: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(text = title, fontSize = 16.sp)
            Text(
                text = description,
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}
