//go:build windows

package main

import (
	"syscall"
	"unsafe"
)

// avisar mostra a caixa de mensagem do Windows (o programa não tem console).
func avisar(titulo, texto string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	caixa := user32.NewProc("MessageBoxW")
	t, _ := syscall.UTF16PtrFromString(titulo)
	m, _ := syscall.UTF16PtrFromString(texto)
	caixa.Call(0, uintptr(unsafe.Pointer(m)), uintptr(unsafe.Pointer(t)), 0x40) // MB_ICONINFORMATION
}
