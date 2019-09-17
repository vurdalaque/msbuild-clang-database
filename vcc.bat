@if exist ./compile_commands.json (
	@set NVIM_GUI="running"
	@start nvim-qt.exe ./compile_commands.json %*
) else (
	@echo no compile_commands.json found
)
