package com.visionos.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

private enum class ConnectionMethod(val label: String, val description: String) {
    RTMP_PUSH(
        "RTMP Push (recommended)",
        "Works with most Hikvision/Dahua/Uniview DVRs. No port forwarding, no extra device -- your DVR pushes the stream to us."
    ),
    RTSP(
        "RTSP URL",
        "For cameras reachable directly by URL (e.g. rtsp://user:pass@192.168.1.50:554/stream1)."
    ),
    DAHUA_P2P(
        "Dahua P2P (experimental)",
        "Same login as the DMSS app (serial + username + password). Unverified against real hardware -- may not work yet."
    ),
}

private val CAMERA_MODES = listOf("indoor", "outdoor", "parking", "shop")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddCameraScreen(
    api: VisionOSApi,
    onDone: () -> Unit,
    onBack: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val clipboard = LocalClipboardManager.current

    var name by remember { mutableStateOf("") }
    var mode by remember { mutableStateOf(CAMERA_MODES.first()) }
    var modeMenuExpanded by remember { mutableStateOf(false) }
    var method by remember { mutableStateOf(ConnectionMethod.RTMP_PUSH) }

    var rtspUrl by remember { mutableStateOf("") }
    var p2pSerial by remember { mutableStateOf("") }
    var p2pUsername by remember { mutableStateOf("") }
    var p2pPassword by remember { mutableStateOf("") }

    var isSubmitting by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var createdPushUrl by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Add Camera") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { innerPadding ->
        if (createdPushUrl != null) {
            // Post-creation instructions for RTMP push -- the user needs
            // to copy this into their DVR's Platform Access/RTMP menu.
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    "Camera added",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(Modifier.height(12.dp))
                Text(
                    "Open your DVR's menu, find \"Platform Access\", \"RTMP\", or \"Push Stream\", and enter this URL:",
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                )
                Spacer(Modifier.height(16.dp))
                Card(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            createdPushUrl!!,
                            modifier = Modifier.weight(1f),
                            fontSize = 13.sp
                        )
                        IconButton(onClick = {
                            clipboard.setText(AnnotatedString(createdPushUrl!!))
                        }) {
                            Icon(Icons.Default.ContentCopy, contentDescription = "Copy")
                        }
                    }
                }
                Spacer(Modifier.height(24.dp))
                Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) {
                    Text("Done")
                }
            }
            return@Scaffold
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Camera name") },
                placeholder = { Text("e.g. Front Gate") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(Modifier.height(16.dp))

            ExposedDropdownMenuBox(
                expanded = modeMenuExpanded,
                onExpandedChange = { modeMenuExpanded = it }
            ) {
                OutlinedTextField(
                    value = mode,
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("Mode") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = modeMenuExpanded) },
                    modifier = Modifier
                        .menuAnchor()
                        .fillMaxWidth()
                )
                ExposedDropdownMenu(
                    expanded = modeMenuExpanded,
                    onDismissRequest = { modeMenuExpanded = false }
                ) {
                    CAMERA_MODES.forEach { option ->
                        DropdownMenuItem(
                            text = { Text(option) },
                            onClick = { mode = option; modeMenuExpanded = false }
                        )
                    }
                }
            }

            Spacer(Modifier.height(24.dp))
            Text("Connection method", fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))

            ConnectionMethod.entries.forEach { option ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = if (method == option)
                            MaterialTheme.colorScheme.primaryContainer
                        else MaterialTheme.colorScheme.surfaceVariant
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalAlignment = Alignment.Top
                    ) {
                        RadioButton(selected = method == option, onClick = { method = option })
                        Spacer(Modifier.width(4.dp))
                        Column {
                            Text(option.label, fontWeight = FontWeight.Medium, fontSize = 14.sp)
                            Text(
                                option.description,
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(16.dp))

            when (method) {
                ConnectionMethod.RTMP_PUSH -> {
                    Text(
                        "No details needed now -- we'll generate a unique push URL after you tap Add Camera.",
                        fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                ConnectionMethod.RTSP -> {
                    OutlinedTextField(
                        value = rtspUrl,
                        onValueChange = { rtspUrl = it },
                        label = { Text("RTSP URL") },
                        placeholder = { Text("rtsp://user:pass@192.168.1.50:554/stream1") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                ConnectionMethod.DAHUA_P2P -> {
                    OutlinedTextField(
                        value = p2pSerial,
                        onValueChange = { p2pSerial = it },
                        label = { Text("Device serial number") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = p2pUsername,
                        onValueChange = { p2pUsername = it },
                        label = { Text("Username") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = p2pPassword,
                        onValueChange = { p2pPassword = it },
                        label = { Text("Password") },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }

            if (errorMessage != null) {
                Spacer(Modifier.height(16.dp))
                Text(errorMessage!!, color = MaterialTheme.colorScheme.error, fontSize = 14.sp)
            }

            Spacer(Modifier.height(24.dp))

            val canSubmit = name.isNotBlank() && !isSubmitting && when (method) {
                ConnectionMethod.RTMP_PUSH -> true
                ConnectionMethod.RTSP -> rtspUrl.isNotBlank()
                ConnectionMethod.DAHUA_P2P -> p2pSerial.isNotBlank() && p2pUsername.isNotBlank() && p2pPassword.isNotBlank()
            }

            Button(
                onClick = {
                    errorMessage = null
                    isSubmitting = true
                    scope.launch {
                        try {
                            val request = CreateCameraRequest(
                                name = name,
                                mode = mode,
                                connectionType = when (method) {
                                    ConnectionMethod.RTMP_PUSH -> "rtmp_push"
                                    ConnectionMethod.RTSP -> "rtsp"
                                    ConnectionMethod.DAHUA_P2P -> "dahua_p2p"
                                },
                                rtspUrl = rtspUrl.ifBlank { null },
                                p2pSerial = p2pSerial.ifBlank { null },
                                p2pUsername = p2pUsername.ifBlank { null },
                                p2pPassword = p2pPassword.ifBlank { null }
                            )
                            val response = api.createCamera(request)
                            if (response.rtmpPushUrl != null) {
                                createdPushUrl = response.rtmpPushUrl
                            } else {
                                onDone()
                            }
                        } catch (e: Exception) {
                            errorMessage = "Couldn't add camera: ${e.message}"
                        } finally {
                            isSubmitting = false
                        }
                    }
                },
                enabled = canSubmit,
                modifier = Modifier.fillMaxWidth()
            ) {
                if (isSubmitting) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp))
                } else {
                    Text("Add Camera")
                }
            }
        }
    }
}
